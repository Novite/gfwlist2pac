#!/usr/bin/env python
# -*- coding: utf-8 -*-

##
# gfwlist2pac 0.0.1
# Description: 自动代理配置(Proxy Auto-config)文件生成器，基于gfwlist。
# Author: Vangie DU http://codelife.me
# Source: https://github.com/vangie/gfwlist2pac
# Fork From: https://github.com/JinnLynn/GenPAC
# Original Author: JinnLynn http://jeeker.net
# License: CC BY 3.0 
#          http://creativecommons.org/licenses/by/3.0/
##

# ********************************************************************** #

VERSION = '0.0.1'

defaultConfig = {
    'gfwUrl'         : 'https://raw.githubusercontent.com/gfwlist/gfwlist/master/gfwlist.txt',
    'gfwProxy'       : 'SOCKS5 127.0.0.1:7070',
    'httpProxy'      : 'DIRECT; SOCKS 127.0.0.1:7070; PROXY 127.0.0.1:8087',
    'httpsProxy'     : 'DIRECT; SOCKS 127.0.0.1:7070; PROXY 127.0.0.1:8087',
    'defaultProxy'   : 'DIRECT; PROXY 127.0.0.1:58118',
    'direct'         : 'DIRECT; PROXY 127.0.0.1:58118',
    'pacFilename'    : 'autoproxy.pac',
    'debug'          : False
}


import sys, os, base64, re, ConfigParser, time

def parseConfig(defaultConfig):
    cfgFile = 'gfwlist2pac.cfg'
    if not os.path.exists(cfgFile):
        config = defaultConfig
    else:
        cf = ConfigParser.ConfigParser(defaultConfig);
        cf.read(cfgFile)
        try:
            config = {
                'gfwUrl'         : cf.get('config', 'gfwUrl'),
                'gfwProxy'       : cf.get('config', 'gfwProxy'),
                'httpProxy'      : cf.get('config', 'httpProxy'),
                'httpsProxy'     : cf.get('config', 'httpsProxy'),
                'defaultProxy'   : cf.get('config', 'defaultProxy'),
                'direct'         : cf.get('config', 'direct'),
                'pacFilename'    : cf.get('config', 'pacFilename'),
                'debug'          : cf.get('config', 'debug') in ['true', 'True']
            }
        except Exception, e:
            print e
    if len(config['gfwProxy']) == 0:
        config['gfwProxyType'] = 0
    else:
        p = re.compile('(PROXY|SOCKS|SOCKS5) (?:(.+):(.+)@)?(.+):(\d+)', re.IGNORECASE)
        m = p.match(config['gfwProxy'])
        if m is None:
            print 'Config -> gfwProxy:%s is error format. format like this "PROXY|SOCKS|SOCKS5 [username:password@]hostname:port"' % config['gfwProxy']
            sys.exit(1)
        config['gfwProxyType'] = {
            'SOCKS'     : 1,
            'SOCKS4'    : 1,
            'SOCKS5'    : 2,
            'PROXY'     : 3,
            }[m.group(1).upper()]
        config['gfwProxyUsr'] = m.group(2)
        config['gfwProxyPwd'] = m.group(3)
        config['gfwProxyHost'] = m.group(4)
        config['gfwProxyPort'] = int(m.group(5))

    return config

def printConfigInfo(config):
    print "配置信息: "
    print 'GFWList Proxy: Type: %s, Host: %s, Port: %s , Usr: %s, Pwd: %s' % (config['gfwProxyType'],
                                                                              config['gfwProxyHost'], config['gfwProxyPort'],
                                                                              config['gfwProxyUsr'], config['gfwProxyPwd'])
    print "PAC direct connection String: %s" % config['direct']
    print "PAC Http Proxy String: %s" % config['httpProxy']
    print "PAC Https Proxy String: %s" % config['httpsProxy']
    print "PAC default Proxy String: %s" % config['defaultProxy']

def fetchGFWList(config):
    import socks, socket, urllib2
    gfwProxyType = config['gfwProxyType']
    if (gfwProxyType == socks.PROXY_TYPE_SOCKS4) or (gfwProxyType == socks.PROXY_TYPE_SOCKS5) or (gfwProxyType == socks.PROXY_TYPE_HTTP):
        socks.setdefaultproxy(gfwProxyType, config['gfwProxyHost'], config['gfwProxyPort'], True, config['gfwProxyUsr'], config['gfwProxyPwd'])
        socket.socket = socks.socksocket

    if config['debug']:
        httpHandler = urllib2.HTTPHandler(debuglevel=1)
        httpsHandler = urllib2.HTTPSHandler(debuglevel=1)
        opener = urllib2.build_opener(httpHandler, httpsHandler)
        urllib2.install_opener(opener)

    response = urllib2.urlopen(config['gfwUrl'])
    gfwlistModified = response.info().getheader('last-modified')
    gfwlistContent = response.read()

    return gfwlistContent, gfwlistModified

def wildcardToRegexp(pattern):
    pattern = re.sub(r"([\\\+\|\{\}\[\]\(\)\^\$\.\#])", r"\\\1", pattern);
    #pattern = re.sub(r"\*+", r"*", pattern)
    pattern = re.sub(r"\*", r".*", pattern)
    pattern = re.sub(r"\？", r".", pattern)
    return pattern;

def parseRuleList(ruleList):
    directWildcardList = []
    directRegexpList = []
    proxyWildcardList = []
    proxyRegexpList = []
    for line in ruleList.splitlines()[1:]:
        # 忽略注释
        if (len(line) == 0) or (line.startswith("!")) or (line.startswith("[")):
            continue

        isDirect = False
        isRegexp = True

        origin_line = line

        # 例外
        if line.startswith("@@"):
            line = line[2:]
            isDirect = True

        # 正则表达式语法
        if line.startswith("/") and line.endswith("/"):
            line = line[1:-1]
        elif line.find("^") != -1:
            line = wildcardToRegexp(line)
            line = re.sub(r"\\\^", r"(?:[^\w\-.%\u0080-\uFFFF]|$)", line)
        elif line.startswith("||"):
            line = wildcardToRegexp(line[2:])
            # When using the constructor function, the normal string escape rules (preceding 
            # special characters with \ when included in a string) are necessary. 
            # For example, the following are equivalent:
            # re = new RegExp("\\w+")
            # re = /\w+/
            # via: http://aptana.com/reference/api/RegExp.html
            line = r"^[\\w\\-]+:\\/+(?!\\/)(?:[^\\/]+\\.)?" + line
        elif line.startswith("|") or line.endswith("|"):
            line = wildcardToRegexp(line)
            line = re.sub(r"^\\\|", "^", line, 1)
            line = re.sub(r"\\\|$", "$", line)
        else:
            isRegexp = False

        if not isRegexp:
            if not line.startswith("*"):
                line = "*" + line
            if not line.endswith("*"):
                line += "*"

        if isDirect:
            if isRegexp:
                directRegexpList.append(line)
            else:
                directWildcardList.append(line)
        else:
            if isRegexp:
                proxyRegexpList.append(line)
            else:
                proxyWildcardList.append(line)

        if config['debug']:
            with open('debug_rule.txt', 'a') as f:
                f.write("%s\n\t%s\n\n" % (origin_line, line) )

    return directRegexpList, directWildcardList, proxyRegexpList, proxyWildcardList


def convertListToJSArray(lst):
    lst = filter(lambda s: isinstance(s, (str, unicode)) and len(s) > 0, lst)
    array = "',\n    '".join(lst)
    if len(array) > 0:
        array = "\n    '" + array + "'\n    "
    return '[' + array + ']'

def parseGFWListRules(gfwlistContent):
    gfwlist = base64.decodestring(gfwlistContent)
    if config['debug']:
        with open('debug_gfwlist.txt', 'w') as f:
            f.write(gfwlist)

    return parseRuleList(gfwlist)

def parseUserRules():
    directUserRegexpList = []
    directUserWildcardList = []
    proxyUserRegexpList = []
    proxyUserWildcardList = []
    try:
        with open('gfwlist2pac.rules') as f:
            directUserRegexpList, directUserWildcardList, proxyUserRegexpList, proxyUserWildcardList = parseRuleList(f.read())
    except Exception, e:
        pass

    return directUserRegexpList, directUserWildcardList, proxyUserRegexpList, proxyUserWildcardList

def generatePACRuls(userRules, gfwListRules):
    directRegexpList, directWildcardList, proxyRegexpList, proxyWildcardList = gfwListRules
    directUserRegexpList, directUserWildcardList, proxyUserRegexpList, proxyUserWildcardList = userRules

    rules = '''
// user rules
var directUserRegexpList   = %s;
var directUserWildcardList = %s;
var proxyUserRegexpList    = %s;
var proxyUserWildcardList  = %s;

// gfwlist rules
var directRegexpList   = %s;
var directWildcardList = %s;
var proxyRegexpList    = %s;
var proxyWildcardList  = %s;
''' % ( convertListToJSArray(directUserRegexpList),
        convertListToJSArray(directUserWildcardList),
        convertListToJSArray(proxyUserRegexpList),
        convertListToJSArray(proxyUserWildcardList),
        convertListToJSArray(directRegexpList),
        convertListToJSArray(directWildcardList),
        convertListToJSArray(proxyRegexpList),
        convertListToJSArray(proxyWildcardList)
    )
    return rules


def CreatePacFile(userRules, gfwlistRules, config):
    pacContent = '''/**
 * gfwlist2pac %(ver)s http://codelife.me
 * Generated: %(generated)s
 * GFWList Last-Modified: %(gfwmodified)s
 */

// proxy
var P1 = "%(httpProxy)s";
var P2 = "%(httpsProxy)s";
%(rules)s
function FindProxyForURL(url, host) {
    var D = "%(direct)s";

    var regExpMatch = function(url, pattern) {
        try { 
            return new RegExp(pattern).test(url); 
        } catch(ex) { 
            return false; 
        }
    };
    
    var i = 0;

    for (i in directUserRegexpList) {
        if(regExpMatch(url, directUserRegexpList[i])) return D;
    }

    for (i in directUserWildcardList) {
        if (shExpMatch(url, directUserWildcardList[i])) return D;
    }

    for (i in proxyUserRegexpList) {
        if(regExpMatch(url, proxyUserRegexpList[i]))  {
            if (url.substring(0,5) == "https") 
                return P2;
            else
                return P1;
        }
    }

    for (i in proxyUserWildcardList) {
        if(shExpMatch(url, proxyUserWildcardList[i]))  {
            if (url.substring(0,5) == "https") 
                return P2;
            else
                return P1;
        }
    }

    for (i in directRegexpList) {
        if(regExpMatch(url, directRegexpList[i])) return D;
    }

    for (i in directWildcardList) {
        if (shExpMatch(url, directWildcardList[i])) return D;
    }

    for (i in proxyRegexpList) {
        if(regExpMatch(url, proxyRegexpList[i]))  {
            if (url.substring(0,5) == "https") 
                return P2;
            else
                return P1;
        }
    }

    for (i in proxyWildcardList) {
        if(shExpMatch(url, proxyWildcardList[i]))  {
            if (url.substring(0,5) == "https") 
                return P2;
            else
                return P1;
        }
    }

    return "%(defaultProxy)s";
}
'''
    result = { 'ver'        : VERSION,
               'generated'  : time.strftime('%a, %d %b %Y %H:%M:%S GMT', time.gmtime()),
               'gfwmodified': gfwlistModified,
               'httpProxy'      : config['httpProxy']    ,
               'httpsProxy'      : config['httpsProxy']    ,
               'defaultProxy'      : config['defaultProxy']    ,
               'direct'      : config['direct']    ,
               'rules'      : generatePACRuls(userRules, gfwlistRules)
    }
    pacContent = pacContent % result
    with open(config['pacFilename'], 'w') as handle:
        handle.write(pacContent)


if __name__ == "__main__":

    #更改工作目录为脚本所在目录
    os.chdir(sys.path[0])

    print '''/** 
 * gfwlist2pac %s by Vangie Du http://codelife.me
 */''' % VERSION

    config = parseConfig(defaultConfig)

    printConfigInfo(config)

    print "正在获取GFWList %s ..." % config['gfwUrl']

    try:
        gfwlistContent, gfwlistModified = fetchGFWList(config)
        print "GFWList[Last-Modified: %s]已获取。" % gfwlistModified
        print '正在解析 GFWList Rules ...'
    except Exception as e:
        print "GFWList获取失败，请检查相关内容是否配置正确。"
        print "错误信息: %s" % e.message
        sys.exit(1)

    # 无论gfwlist是否获取成功，都要解析，否则PAC文件有错，只是获取失败时解析的是空数据
    gfwlistRules = parseGFWListRules(gfwlistContent)

    print '正在解析 User Rules ...'
    userRules = parseUserRules()

    print "正在生成 %s ..." % config['pacFilename']
    CreatePacFile(userRules, gfwlistRules, config)

    print "一切就绪。"
