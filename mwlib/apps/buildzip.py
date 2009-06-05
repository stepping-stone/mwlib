
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.txt for additional licensing information.

"""mz-zip - installed via setuptools' entry_points"""

import os
import tempfile
import shutil
import zipfile

def _walk(root):
    retval = []
    for dirpath, dirnames, files in os.walk(root):
        # retval.extend([os.path.normpath(os.path.join(dirpath, x))+"/" for x in dirnames])
        retval.extend([os.path.normpath(os.path.join(dirpath, x)) for x in files])
    retval = [x.replace("\\", "/") for x in retval]
    retval.sort()
    return retval

                     
def zipdir(dirname, output=None):
    """recursively zip directory and write output to zipfile.
    @param dirname: directory to zip
    @param output: name of zip file that get's written
    """
    if not output:
        output = dirname+".zip"

    output = os.path.abspath(output)
    cwd = os.getcwd()
    try:
        os.chdir(dirname)
        files = _walk(".")
        zf = zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED)
        for i in files:
            if i.endswith("/"):
                zf.writestr(zipfile.ZipInfo(i), "")
            else:
                zf.write(i)
        zf.close()
    finally:
        os.chdir(cwd)


def make_nuwiki(fsdir, base_url, metabook, options, podclient=None):
    from mwlib.net import fetch, mwapi
    from mwlib.metabook import get_licenses
    from twisted.internet import reactor,  defer

    if not base_url.endswith("/"):
        base_url += "/"
    api_url = "".join([base_url, "api", options.script_extension])
    if isinstance(api_url,  unicode):
        api_url = api_url.encode("utf-8")

    login = options.login
    username, password, domain = None, None, None
    if login:
        if login.count(':') == 1:
            username, password = unicode(login, 'utf-8').split(':', 1)
        else:
            username, password, domain = unicode(login, 'utf-8').split(':', 2)


    options.fetcher = None # stupid python
    fsout = fetch.fsoutput(fsdir)

    licenses = get_licenses(metabook)

    def get_api():
        api = mwapi.mwapi(api_url)
        if username:
            return api.login(username, password, domain)
        return defer.succeed(api)
    
    def doit(api):
        fsout.dump_json(metabook=metabook)
        nfo = {
            'format': 'nuwiki',
            'base_url': base_url,
            'script_extension': options.script_extension,
        }
        if options.print_template_pattern:
            nfo["print_template_pattern"] = options.print_template_pattern
         
        fsout.dump_json(nfo=nfo)
        
        pages = fetch.pages_from_metabook(metabook)
        options.fetcher = fetch.fetcher(api, fsout, pages,
                                              licenses=licenses,
                                              podclient=podclient,
                                              print_template_pattern=options.print_template_pattern,
                                              template_exclusion_category=options.template_exclusion_category,
                                              imagesize=options.imagesize)

    def start():
        def login_failed(res):
            print "Fatal error: login failed:", res.getErrorMessage()
            reactor.stop()
            return res
        get_api().addErrback(login_failed).addCallback(doit)
        
    try:
        if podclient is not None:
            old_class = podclient.__class__
            podclient.__class__ = fetch.PODClient

        reactor.callLater(0.0, start)
        reactor.run()
    finally:
        if podclient is not None:
            podclient.__class__ = old_class

    
    fetcher = options.fetcher
    if not fetcher:
        raise RuntimeError("Fatal error")
    
    if fetcher.fatal_error:
        print "error:", fetcher.fatal_error
        raise RuntimeError('Fatal error')
    print "done"

        
def make_zip(output=None, options=None, env=None, podclient=None, status=None):
    tmpdir = tempfile.mkdtemp()
    try:
        fsdir = os.path.join(tmpdir, 'nuwiki')
        print 'creating nuwiki in %r' % fsdir
        make_nuwiki(fsdir,
            base_url=env.wiki.url,
            metabook=env.metabook,
            options=options,
            podclient=podclient,
        )

        filename = tempfile.mktemp(suffix=".zip")
        zipdir(fsdir, filename)
        if output:
            os.rename(filename, output)
            filename = output

        if podclient:                
            status(status='uploading', progress=0)
            podclient.post_zipfile(filename)

        return filename

    finally:
        if not options.keep_tmpfiles:
            print 'removing tmpdir %r' % tmpdir
            shutil.rmtree(tmpdir, ignore_errors=True)
        else:
            print 'keeping tmpdir %r' % tmpdir

        
def main():    
    from mwlib.options import OptionParser

    parser = OptionParser()
    parser.add_option("-o", "--output", help="write output to OUTPUT")
    parser.add_option("-p", "--posturl", help="http post to POSTURL (directly)")
    parser.add_option("-g", "--getposturl",
        help='get POST URL from PediaPress.com, open upload page in webbrowser',
        action='store_true',
    )
    parser.add_option('--keep-tmpfiles',                  
        action='store_true',
        default=False,
        help="don't remove  temporary files like images",
    )
    options, args = parser.parse_args()
    
    use_help = 'Use --help for usage information.'
    if parser.metabook is None and options.collectionpage is None:
        parser.error('Neither --metabook nor, --collectionpage or arguments specified.\n' + use_help)
    if options.posturl and options.getposturl:
        parser.error('Specify either --posturl or --getposturl.\n' + use_help)
    if not options.posturl and not options.getposturl and not options.output:
        parser.error('Neither --output, nor --posturl or --getposturl specified.\n' + use_help)
    if options.posturl:
        from mwlib.podclient import PODClient
        podclient = PODClient(options.posturl)
    elif options.getposturl:
        import webbrowser
        from mwlib.podclient import podclient_from_serviceurl
        podclient = podclient_from_serviceurl('http://pediapress.com/api/collections/')
        pid = os.fork()
        if not pid:
            try:
                webbrowser.open(podclient.redirecturl)
            finally:
                os._exit(0)
        import time
        time.sleep(1)
        try:
            os.kill(pid, 9)
        except:
            pass
              
    else:
        podclient = None
    
    from mwlib import utils,  wiki
    
    if options.daemonize:
        utils.daemonize()
    if options.pid_file:
        open(options.pid_file, 'wb').write('%d\n' % os.getpid())

    filename = None
    status = None
    try:
        try:
            env = parser.makewiki()
            from mwlib.status import Status
            status = Status(podclient=podclient, progress_range=(1, 90))
            status(progress=0)
            output = options.output

            if isinstance(env.wiki, wiki.dummy_web_wiki):
                make_zip(output, options, env, podclient=podclient, status=status)
            else:
                raise NotImplementedError("zip file creation from %r not supported" % (env.wiki,))
        except Exception, e:
            if status:
                status(status='error')
            raise
    finally:
        if options.output is None and filename is not None:
            print 'removing %r' % filename
            utils.safe_unlink(filename)
        if options.pid_file:
            utils.safe_unlink(options.pid_file)
