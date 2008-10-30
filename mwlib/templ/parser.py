
# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.

from mwlib.templ.nodes import Node, Variable, Template, IfNode
from mwlib.templ.scanner import symbols, tokenize

def optimize(node):
    if type(node) is tuple:
        return node
    
    if isinstance(node, basestring):
        return node

    if len(node)==1 and type(node) in (list, Node):
        return optimize(node[0])

    if isinstance(node, (Variable, Template, IfNode)):
        return node.__class__(tuple(optimize(x) for x in node))
    else:
        # combine strings
        res = []
        tmp = []
        for x in (optimize(x) for x in node):
            if isinstance(x, basestring) and x!='=':
                tmp.append(x)
            else:
                if tmp:
                    res.append(u''.join(tmp))
                    tmp = []
                res.append(x)
        if tmp:
            res.append(u''.join(tmp))

        node[:] = res
    
    
    if len(node)==1 and type(node) in (list, Node):
        return optimize(node[0])
    
    return node

    
class Parser(object):
    def __init__(self, txt):
        if isinstance(txt, str):
            txt = unicode(txt)
            
        self.txt = txt
        self.tokens = tokenize(txt)
        self.pos = 0

    def getToken(self):
        return self.tokens[self.pos]

    def setToken(self, tok):
        self.tokens[self.pos] = tok


    def variableFromChildren(self, children):
        v=[]

        try:
            idx = children.index(u"|")
        except ValueError:
            v.append(children)
        else:
            v.append(children[:idx])
            v.append(children[idx+1:])

        return Variable(v)
        
    def _eatBrace(self, num):
        ty, txt = self.getToken()
        assert ty == symbols.bra_close
        assert len(txt)>= num
        newlen = len(txt)-num
        if newlen==0:
            self.pos+=1
            return
        
        if newlen==1:
            ty = symbols.txt

        txt = txt[:newlen]
        self.setToken((ty, txt))
        
    def ifnodeFromChildren(self, children):
        children[0] = children[0].split(":", 1)[1]
        args = self._parse_args(children)
        cond = optimize(args[0])
        if not isinstance(cond, unicode):
            if cond and isinstance(cond[0], unicode):
                if not cond[0].strip():
                    del cond[0]

            if cond and isinstance(cond[-1], unicode):
                if not cond[-1].strip():
                    del cond[-1]
        args[0] = cond
        n = IfNode(args)
        return n

    def _parse_args(self, children):
        args = []
        arg = []

        linkcount = 0
        for c in children:
            if c==u'[[':
                linkcount += 1
            elif c==']]':
                linkcount -= 1
            elif c==u'|' and linkcount==0:
                args.append(arg)
                arg = []
                continue
            arg.append(c)


        if arg:
            args.append(arg)

        return [optimize(x) for x in args]
                    
    def templateFromChildren(self, children):
        if children and isinstance(children[0], unicode):
            s = children[0].strip().lower()
            if s.startswith("#if:"):
                return self.ifnodeFromChildren(children)
            
        # find the name
        name = []
        
        idx = 0
        for idx, c in enumerate(children):
            if c==u'|':
                break
            name.append(c)

        name = optimize(name)
        if isinstance(name, unicode):
            name = name.strip()
                    
        args = self._parse_args(children[idx+1:])
        
        return Template([name, tuple(args)])
        
    def parseOpenBrace(self):
        ty, txt = self.getToken()
        n = []

        numbraces = len(txt)
        self.pos += 1
        
        while 1:
            ty, txt = self.getToken()
            if ty==symbols.bra_open:
                n.append(self.parseOpenBrace())
            elif ty is None:
                break
            elif ty==symbols.bra_close:
                closelen = len(txt)
                if closelen==2 or numbraces==2:
                    t=self.templateFromChildren(n)
                    n=[]
                    n.append(t)
                    self._eatBrace(2)
                    numbraces-=2
                else:
                    v=self.variableFromChildren(n)
                    n=[]
                    n.append(v)
                    self._eatBrace(3)
                    numbraces -= 3

                if numbraces==0:
                    break
                elif numbraces==1:
                    n.insert(0, "{")
                    break
            elif ty==symbols.noi:
                self.pos += 1 # ignore <noinclude>
            else: # link, txt
                n.append(txt)
                self.pos += 1                

        return n
        
    def parse(self):
        n = []
        
        while 1:
            ty, txt = self.getToken()
            if ty==symbols.bra_open:
                n.append(self.parseOpenBrace())
            elif ty is None:
                break
            elif ty==symbols.noi:
                self.pos += 1   # ignore <noinclude>
            else: # bra_close, link, txt                
                n.append(txt)
                self.pos += 1
        return n

def parse(txt):
    return optimize(Parser(txt).parse())
