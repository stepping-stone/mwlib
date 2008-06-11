#! /usr/bin/env python

# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.

import simplejson
import zipfile
from mwlib import uparser, parser
import mwlib.log
log = mwlib.log.Log("zip")


class RecordDB(object):
    def __init__(self, db):
        assert db is not None, "db must not be None"
        self.db = db
        self.articles = {}
        self.templates = {}
        
    def getRawArticle(self, name, revision=None):
        r = self.db.getRawArticle(name, revision=revision)
        if r is None:
            return None
        self.articles[name] = {
            'revision': revision,
            'content-type': 'text/x-wiki',
            'content': r,
            'url': self.db.getURL(name, revision=revision),
            'authors': self.db.getAuthors(name, revision=revision),
        }
        return r
    
    def getTemplate(self, name, followRedirects=False):
        r = self.db.getTemplate(name, followRedirects=followRedirects)
        self.templates[name] = {
            'content-type': 'text/x-wiki',
            'content': r,
        }
        return r
    

class ZipfileCreator(object):
    def __init__(self, zf, wikidb=None, imgdb=None):
        self.zf = zf
        self.db = RecordDB(wikidb)
        self.images = {}
        self.imgdb = imgdb

    def addObject(self, name, value):
        """
        @type name: unicode
        
        @type value: str
        """
        
        self.zf.writestr(name.encode('utf-8'), value)
    
    def addArticle(self, title, revision=None):
        a = uparser.parseString(title, revision=revision, wikidb=self.db)
        for x in a.allchildren():
            if isinstance(x, parser.ImageLink):
                name = x.target
                self.images[name] = {}
    
    def writeImages(self, size=None, progress_callback=None):
        """
        @param progress_callback: callback which gets called with two args: the
            number of the currently processed image and the total number of
            images (optional)
        @type progress_callback: callable
        """
        if self.imgdb is None:
            return
        
        image_names = sorted(self.images.keys())
        n = len(image_names)
        for i, name in enumerate(image_names):
            if progress_callback is not None:
                progress_callback(i, n)
            dp = self.imgdb.getDiskPath(name, size=size)
            if dp is None:
                continue
            self.zf.write(dp, (u"images/%s" % name.replace("'", '-')).encode("utf-8"))
            self.images[name]['url'] = self.imgdb.getURL(name, size=size)
            try:
                descriptionurl = self.imgdb.getDescriptionURL(name)
                if descriptionurl:
                    self.images[name]['descriptionurl'] = descriptionurl
            except AttributeError:
                pass
            license = self.imgdb.getLicense(name)
            if license:
                self.images[name]['license'] = license
    
    def writeContent(self):
        self.addObject('content.json', simplejson.dumps(dict(
            articles=self.db.articles,
            templates=self.db.templates,
            images=self.images,
        )))
    
