import hashlib
import json
import os
import time
from os.path import join, getsize

import psutil
import requests

import tools.globalvar as gl
from tools.RecheckReport import RecheckReport, RecheckAllReport, checkDirReport
from tools.ReseedInfoJson import ReseedInfoJson
from tools.TorrentInfo import get_torrent_name
from tools.dirmanager import getemptydirlist, deletedir
from tools.qbapi import qbapi
from tools.sid import supportsid, getsidname, getnamesid


class Manager(object):

    def __init__(self, config=None):
        basepath = 'autopt/appdata/'
        self.reseedcategory = 'Reseed'
        self.rechecklistname = basepath + 'ReChecklist.csv'
        self.reseedjsonname = basepath + 'ReSeedRecord.json'
        self.logger = gl.get_value('logger').logger
        self.qbapi = qbapi(gl.get_value('config').qbtaddr, gl.get_value('config').qbtusername,
                           gl.get_value('config').qbtpassword)

        self.recheckreport = RecheckReport()
        self.recheckallreport = RecheckAllReport()

        self._session = requests.session()
        self._session.headers = {
            'User-Agent': 'Mozilla/5.0 AppleWebKit/537.36 Chrome/79.0.3945.16 Safari/537.36 Edg/79.0.309.11'
        }
        # 4.1.9 -> 2.2.1
        # 4.2.5 -> 2.5.1
        apiversion = self.qbapi.webapiVersion().strip()
        if apiversion not in ['2.2.0', '2.2.1', '2.3.0', '2.4.0', '2.4.1', '2.5.0', '2.5.1', '2.6.0', '2.6.1', '2.6.1',
                              '2.8.0', '2.8.1', '2.8.2']:
            self.logger.warning('不支持的qb api版本' + apiversion)
            exit(7)

        if config is not None and config['name'] != 'reseed':
            self.config = config
            self.dynamiccapacity = self.config['capacity']
            self.maincategory = self.config['maincategory']
            self.subcategory = self.config['subcategory']
            self.diskletter = ''
            self.getcategory()
        # else:
        # Reseed
        self.stationref = gl.get_value('allref')['ref']
        self.dlcategory = []
        self.allcategory = []
        self.getallcategory(gl.get_value('config').qbtignore)

    def getallcategory(self, ignore: []):
        listjs = self.qbapi.category()

        for key, value in listjs.items():
            if key in ignore:
                continue
            self.allcategory.append(key)
        allconfig = gl.get_value('config')['all']
        for key, value in allconfig.items():
            if value['switch']:
                if value['maincategory'] in self.allcategory and value['maincategory'] not in self.dlcategory:
                    self.dlcategory.append(value['maincategory'])
                for val in value['subcategory']:
                    if val in self.allcategory and val not in self.dlcategory:
                        self.dlcategory.append(val)

    def getcategory(self):
        if self.maincategory == '':
            self.logger.info('no maincategory')
            return
        listjs = self.qbapi.category()

        self.logger.info('maincategory:' + self.maincategory)
        if self.maincategory in listjs:
            self.diskletter = listjs[self.maincategory]['savePath'][0]
            self.logger.info('diskletter:' + self.diskletter)
        else:
            self.logger.error('category ' + self.maincategory + ' is not exist!!!!')
            exit(2)

        tempcategory = []
        self.logger.info('Befor filter subcategory:' + ','.join(self.subcategory))
        for val in self.subcategory:
            if val in listjs and listjs[val]['savePath'][0] == self.diskletter:
                tempcategory.append(val)
        self.subcategory = tempcategory
        self.logger.info('After filter subcategory:' + ','.join(self.subcategory))

    def checksize(self, filesize):
        res = True
        if self.config['capacity'] != 0:
            self.logger.info('Torrent Files Total Size =' + str(filesize) + 'GB')

            gtl = self.gettorrentlist()
            nowtotalsize, pretotalsize = self.gettotalsize(gtl)
            self.logger.debug('nowtotalsize =' + str(nowtotalsize) + 'GB')
            self.logger.debug('pretotalsize =' + str(pretotalsize) + 'GB')

            diskremainsize = 1048576  # 设置无穷大的磁盘大小为1PB=1024*1024GB
            if self.diskletter != '':
                # 留出50G容量防止空间分配失败
                diskremainsize = self.getdiskleftsize(self.diskletter) - 50 - (pretotalsize - nowtotalsize)
                self.logger.debug('diskremainsize =' + str(diskremainsize) + 'GB')
            self.dynamiccapacity = self.config['capacity'] \
                if pretotalsize + diskremainsize > self.config['capacity'] else pretotalsize + diskremainsize
            self.logger.info('dynamiccapacity =' + str(self.dynamiccapacity) + 'GB')

            if filesize > self.dynamiccapacity:
                self.logger.warning('Too big !!! filesize(' + str(filesize) + 'GB) > dynamic capacity(' +
                                    str(self.dynamiccapacity) + 'GB)')
                return False

            stlist, res = self.selecttorrent(filesize, gtl, pretotalsize)
            if not self.deletetorrent(stlist):
                self.logger.error('Error when delete torrent')
                return False
        return res

    def deletetorrent(self, stlist, deleteFiles=True):
        ret = True
        if isinstance(stlist, str):
            stlist = [(stlist, [])]
        alllist = []
        filescount = 0
        for val in stlist:
            filescount += len(self.qbapi.torrentFiles(val[0]))
            alllist.append(val[0])
            alllist += val[1]
        if len(alllist) != 0:
            self.logger.info('删除种子.' + ",".join(alllist))
        if not self.qbapi.torrentsDelete(alllist, deleteFiles):
            ret = False
        # 每个文件延迟0.3333秒
        # time.sleep(filescount / 3)

        jsonlist = {}
        updatefile = False
        if len(stlist) and os.path.exists(self.reseedjsonname):
            jsonlist = {}
            with open(self.reseedjsonname, 'r', encoding='UTF-8')as f:
                jsonlist = json.loads(f.read())
            for val in stlist:
                if val[0] in jsonlist:
                    updatefile = True
                    del jsonlist[val[0]]
                for rsval in val[1]:
                    if rsval in jsonlist:
                        self.logger.error('出问题了，辅种信息不应该出现在主种信息里.' + rsval)
                        updatefile = True
                        del jsonlist[rsval]
        if updatefile:
            with open(self.reseedjsonname, 'w', encoding='UTF-8')as f:
                f.write(json.dumps(jsonlist))

        newstr = ''
        updatefile = False
        if len(stlist) and os.path.exists(self.rechecklistname):
            with open(self.rechecklistname, 'r', encoding='UTF-8') as f:
                for line in f.readlines():
                    rct = line.strip().split(',')
                    if rct[3] in alllist:
                        updatefile = True
                    else:
                        newstr += line
        if updatefile:
            with open(self.rechecklistname, 'w', encoding='UTF-8') as f:
                f.write(newstr)

        return ret

    def gettotalsize(self, gtl):
        predict_sumsize = 0
        now_sumsize = 0
        for val in gtl:
            predict_sumsize += val['size']
            now_sumsize += val['size'] if val['progress'] == 1 else self.getdirsize(val['save_path'] + val['name'])
        now_sumsize /= (1024 * 1024 * 1024)
        predict_sumsize /= (1024 * 1024 * 1024)
        self.logger.debug('predict torrent sum size =' + str(predict_sumsize) + 'GB')
        self.logger.debug('now torrent sum size =' + str(now_sumsize) + 'GB')
        return now_sumsize, predict_sumsize

    def selecttorrent(self, filesize, gtl, totalsize):
        deletesize = totalsize + filesize - self.dynamiccapacity
        self.logger.info('deletesize = ' + str(deletesize) + 'GB')
        d_list = []
        now = time.time()
        # need delete
        if deletesize > 0 and len(gtl) > 0:
            # 不删除 keeptorrenttime 小时内下载的种子
            infinte_lastactivity = [val for val in gtl
                                    if val['last_activity'] > now and
                                    now - val['added_on'] > self.config['keeptorrenttime'] * 60 * 60]
            # infinte_lastactivity.sort(key=lambda x: x['added_on'])
            # reseedhash
            infinte_lastactivity = self.sortfilterwithreseed(infinte_lastactivity, 'added_on')
            # print (infinte_lastactivity)
            for val in infinte_lastactivity:
                d_list.append((val['hash'], val['reseedlist']))
                deletesize -= val['size'] / 1024 / 1024 / 1024
                self.logger.info(
                    'select torrent name:\"' + val['name'] + '\"  size=' + str(
                        val['size'] / 1024 / 1024 / 1024) + 'GB, Reseed count:' + str(len(val['reseedlist'])))
                if deletesize < 0:
                    break
            self.logger.info('torrent select part 1 , list len = ' + str(len(d_list)))
        if deletesize > 0 and len(gtl) > 0:
            # 不删除 keeptorrenttime 小时内下载的种子
            other_lastactivity = [val for val in gtl
                                  if val['last_activity'] <= now and
                                  now - val['added_on'] > self.config['keeptorrenttime'] * 60 * 60]
            # other_lastactivity.sort(key=lambda x: x['last_activity'])
            #  reseedhash
            other_lastactivity = self.sortfilterwithreseed(other_lastactivity, 'last_activity')
            for val in other_lastactivity:
                d_list.append((val['hash'], val['reseedlist']))
                deletesize -= val['size'] / 1024 / 1024 / 1024
                self.logger.info(
                    'select torrent name:\"' + val['name'] + '\"  size=' + str(
                        val['size'] / 1024 / 1024 / 1024) + 'GB, Reseed count:' + str(len(val['reseedlist'])))
                if deletesize < 0:
                    break
            self.logger.info('torrent select part 2 , list len = ' + str(len(d_list)))
        if deletesize > 0:
            self.logger.info('deletesize > 0, 不满足条件, 不删除')
            d_list = []
            return d_list, False
        else:
            return d_list, True

    def gettorrentlist(self):
        listjs = []
        if self.maincategory != '':
            info = self.qbapi.torrentsInfo(category=self.maincategory)
            listjs = info
            for val in self.subcategory:
                info = self.qbapi.torrentsInfo(category=val)
                listjs += info
        else:
            listjs = self.qbapi.torrentsInfo(sort='last_activity')
        return listjs

    def istorrentexist(self, thash):
        return len(self.qbapi.torrentInfo(thash)) > 0

    def gettorrentdlstatus(self, thash):
        tinfo = self.qbapi.torrentInfo(thash)
        # 修复程序速度太快QBAPI未能获取到种子信息
        if len(tinfo) == 0:
            return False
        tstate = tinfo['state']
        self.logger.debug('torrent state:' + tstate)
        if tstate in ['downloading', 'pausedDL', 'queuedDL', 'uploading', 'pausedUP', 'queuedUP', 'stalledUP',
                      'forcedUP', 'stalledDL', 'forceDL', 'checkingUP', 'checkingDL']:
            return True
        else:
            # error missingFiles allocating metaDL  checkingResumeData moving unknown
            return False

    def istorrentdlcom(self, thash):
        tinfo = self.qbapi.torrentInfo(thash)
        if len(tinfo) == 0:
            self.logger.debug('Cannot find torrent' + thash + '. Maybe already deleted')
            return False
        # api 2.3 4294967295
        # api 2.4 -28800
        if tinfo['completion_on'] == 4294967295 or tinfo['completion_on'] < 0:
            return False
        else:
            return True

    def istorrentcheckcom(self, thash):
        tinfo = self.qbapi.torrentInfo(thash)
        if len(tinfo) == 0:
            self.logger.debug('Cannot find torrent' + thash + '. Maybe already deleted')
            return -1
        tstate = tinfo['state']
        self.logger.debug('torrent state:' + tstate)
        if tstate in ['downloading', 'pausedDL', 'queuedDL', 'stalledDL', 'forceDL', 'missingFiles', 'metaDL',
                      'allocating']:
            return 0
        elif tstate in ['checkingDL', 'checkingUP', 'checkingResumeData', 'moving']:
            return 1
        elif tstate in ['uploading', 'pausedUP', 'queuedUP', 'stalledUP', 'forcedUP']:
            return 2
        else:
            # error moving unknown
            return -1

    def gettorrentname(self, thash):
        tinfo = self.qbapi.torrentInfo(thash)
        if len(tinfo) == 0:
            return ''
        return tinfo['name']

    def gettorrentcategory(self, thash):
        tinfo = self.qbapi.torrentInfo(thash)
        if len(tinfo) == 0:
            return ''
        return tinfo['category']
        # self.logger.debug('torrent category:' + tcategory)

    def checktorrenttracker(self, thash):
        trackers = [val['url'] for val in self.qbapi.torrentTrackers(thash) if val['status'] != 0]
        for val in trackers:
            if val.find('https') != 0 and val.find('http') == 0:
                new = val[:4] + 's' + val[4:]
                self.qbapi.editTracker(thash, val, new)
                self.logger.info('更新tracker的http为https')

    def addtorrent(self, content, thash, page):
        # 判断种子是否存在
        if not self.istorrentexist(thash):

            # 如果是新种或者服务器无返回结果，或者查询失败，则直接下载
            if page.createtimestamp > 1800:
                inquery = self.inqueryreseed(thash)
                if self.addpassivereseed(thash, inquery, content, page.id):
                    return True

            # 下载分配空间
            if not self.checksize(page.size):
                return

            if self.qbapi.addNewTorrentByBin(content, paused=False, category=self.maincategory, autoTMM=True,
                                             upLimit=self.config['uploadspeedlimit'] * 1024 * 1024 / 8):
                self.logger.info('addtorrent successfully info hash = ' + thash)
                # 添加辅种功能后不再等待，否则经常在此等待
                # 防止磁盘卡死,当磁盘碎片太多或磁盘负载重时此处会卡几到几十分钟
                # while not self.gettorrentdlstatus(thash):
                #     time.sleep(5)
                time.sleep(2)
                # 删除匹配的tracker,暂时每个种子都判断不管是哪个站点
                self.removematchtracker(thash, 'pttrackertju.tjupt.org')
                self.removematchtracker(thash, 'tracker-campus.tjupt.org')
                # gl.get_value('wechat').send(text='添加种子中断检查tracker断点')

                self.checktorrenttracker(thash)
                # self.qbapi.resumeTorrents(thash)
                with open(self.rechecklistname, 'a', encoding='UTF-8')as f:
                    f.write(self.config['name'] + ',' + page.id + ',' + 'dl' + ',' + thash + ',' + str(
                        page.futherstamp) + ',' + 'f' + '\n')
                return True
            return False
        else:
            self.logger.warning('torrent already exist hash=' + thash)
            #  若种子已存在，是否在下载目录、辅种目录、其他目录
            #  如果在下载目录，则已经为主，不动作
            #  如果在辅种目录，看主在哪个目录，若在下载目录，则换分类，若在辅种目录，报错！若在其他目录，则不动作
            #  如果在其他目录，则已经为主，不动作
            self.inctpriority(thash, self.maincategory)
            return True

    # 返回单位大小为Byte
    def getdirsize(self, tdir):
        size = 0
        if os.path.isdir(tdir):
            for root, dirs, files in os.walk(tdir):
                size += sum([getsize('\\\\?\\' + join(root, name)) for name in files])
        elif os.path.isfile(tdir):
            size += getsize(tdir)
        elif os.path.isfile(tdir + '.!qB'):
            size += getsize(tdir + '.!qB')
        return size

    def getdiskleftsize(self, diskletter):
        p = psutil.disk_usage(diskletter + ':\\')[2] / 1024 / 1024 / 1024
        # self.logger.info(self.diskletter + '盘剩余空间' + str(p) + 'GB')
        return p

    def checktorrentdtanddd(self, thash):
        ret = True
        if not self.istorrentdlcom(thash):
            ret = False
            self.deletetorrent(thash)
        return ret

    def removematchtracker(self, thash, trackerstr):
        trackerlist = [val['url'] for val in self.qbapi.torrentTrackers(thash) if val['status'] != 0]
        for val in trackerlist:
            if trackerstr in val:
                self.qbapi.removeTrackers(thash, val)

    def sortfilterwithreseed(self, tlist, method):
        temptlist = []
        with open(self.reseedjsonname, 'r', encoding='UTF-8') as f:
            jsonlist = json.loads(f.read())
            for val in tlist:
                if val['hash'] in jsonlist:
                    rsinfolist = jsonlist[val['hash']]['rslist']
                    isincommonct = True
                    rss = {}
                    for rs in rsinfolist:
                        # 校验失败的不用选择
                        if rs['status'] == 2:
                            continue
                        rsca = self.qbapi.torrentInfo(rs['hash'])
                        # 换了目录的话就跳过删除
                        if not (rsca['category'] in self.dlcategory or rsca['category'] == self.reseedcategory):
                            isincommonct = False
                            break
                        rss[rs['hash']] = rsca
                    if isincommonct:
                        sumtime = val[method]
                        i = 1
                        rslisthash = []
                        for rs in rsinfolist:
                            if rs['hash'] in rss:
                                rslisthash.append(rs['hash'])
                                if method == 'last_activity' and rss[rs['hash']][method] > time.time():  # 没有活动过不能计算进去
                                    continue
                                sumtime += rss[rs['hash']][method]
                                i += 1
                        avergetime = sumtime / i
                        val[method] = avergetime
                        val['reseedlist'] = rslisthash
                        temptlist.append(val)
                else:
                    val['reseedlist'] = []
                    temptlist.append(val)
            if method == 'added_on':
                temptlist.sort(key=lambda x: x['added_on'])
            elif method == 'last_activity':
                temptlist.sort(key=lambda x: x['last_activity'])
        return temptlist

    #  若种子已存在，是否在下载目录、辅种目录、其他目录
    #  如果在下载目录，则已经为主，不动作
    #  如果在辅种目录，看主在哪个目录，若在下载目录，则转换并文件链接，若在辅种目录，报错！若在其他目录，则不动作
    #  如果在其他目录，则已经为主，不动作
    def inctpriority(self, thash, category):
        jsonlist = {}
        rsca = self.qbapi.torrentInfo(thash)
        # 若种子已存在辅种目录
        if rsca['category'] == self.reseedcategory:
            # 在则检查主辅，
            with open(self.reseedjsonname, 'r', encoding='UTF-8') as f:
                jsonlist = json.loads(f.read())
            # 这里应该为辅，如果没有人为操作
            if not thash in jsonlist:
                hasfound = False
                temp = None
                for k, v in jsonlist.items():
                    for idx, val in enumerate(v['rslist']):
                        if val['hash'] == thash:
                            hasfound = True
                            temp = (k, idx)
                            break
                # 应该能找到，不能找到则有问题
                if hasfound:

                    # ----------testing
                    if jsonlist[temp[0]]['rslist'][temp[1]]['status'] == 0:
                        # gl.get_value('wechat').send(text='程序断点提醒---已存在种子情况分析处理')
                        self.changechecklistrs(thash)
                        return

                    # 若有主，主是否在下载目录，如果是，则转换，如果不是，则此种子已经为辅，不必换
                    rsca = self.qbapi.torrentInfo(temp[0])
                    if rsca['category'] in self.dlcategory or rsca['category'] == self.reseedcategory:
                        # 如果是，则转换
                        listinfo = jsonlist[temp[0]]
                        del jsonlist[temp[0]]
                        origininfo = listinfo['info']
                        origininfo['status'] = 1
                        rslist = listinfo['rslist']
                        newinfo = {'info': rslist[temp[1]]}
                        del rslist[temp[1]]
                        rslist.append(origininfo)
                        del newinfo['info']['status']
                        newinfo['rslist'] = rslist
                        jsonlist[thash] = newinfo
                        # 由于各种种子活动状态的不确定性，容易导致移动文件卡死，大文件跨分区的话还容易浪费硬盘性能，目前解决方案为换分类不换目录
                        self.changerstcategory(rsca, {'hash': thash}, rtcategory=category)

                        with open(self.reseedjsonname, 'w', encoding='UTF-8') as f:
                            f.write(json.dumps(jsonlist))
                else:
                    # 不能找到的话有可能是刚刚添加进去的辅种，还没有录入json里
                    # self.logger.error('没找找到种子信息，出问题了')
                    exit(6)
            else:
                self.logger.error('此种子已是主种')
                # exit(5)
        elif rsca['category'] in self.dlcategory:
            self.logger.debug('此种子已在下载目录！')
        else:
            self.logger.debug('此种子已在其他目录！')

    def createhardfiles(self, srcpath, srcname, content, dst, hash, name):
        #  防止文件名里符号/\:*?"<>|,这在文件里是不允许存在的,将会被qb设置成_
        name = name.replace('/', '_').replace('\\', '_').replace(':', '_').replace('*', '_') \
            .replace('?', '_').replace('"', '_').replace('<', '_').replace('>', '_').replace('|', '_')
        dst = dst + hash
        # if os.path.exists(dst+hash):
        #     return
        for idx, val in enumerate(content):
            content[idx]['name'] = content[idx]['name'].replace('/', '\\')
        if len(content) == 0:
            self.logger.error('路径为空，创建失败')
            return False
        # 判断\\防止目录+单文件形式
        elif len(content) == 1 and ('\\' not in content[0]['name']):
            os.makedirs('\\\\?\\' + dst, exist_ok=True)
            try:
                os.link('\\\\?\\' + srcpath + content[0]['name'], '\\\\?\\' + dst + '\\' + name)
            except FileExistsError as e:
                self.logger.warning(e)
            except FileNotFoundError as e:
                self.logger.warning('链接失败，尝试使用后缀.!qB链接')
                try:
                    os.link('\\\\?\\' + srcpath + content[0]['name'] + '.!qB', '\\\\?\\' + dst + '\\' + name)
                except FileExistsError as _e:
                    self.logger.error(_e)
                except BaseException as _e:
                    self.logger.error(_e)
                    return False

        else:
            dst = dst + '\\' + name
            srcnamelen = len(srcname)
            # os.makedirs(dst, exist_ok=True)
            for val in content:
                dirname, basename = os.path.split(val['name'])

                os.makedirs('\\\\?\\' + dst + dirname[srcnamelen:], exist_ok=True)
                try:
                    os.link('\\\\?\\' + srcpath + val['name'],
                            '\\\\?\\' + dst + dirname[srcnamelen:] + '\\' + basename)
                except FileExistsError as e:
                    self.logger.warning(e)
                except FileNotFoundError as e:
                    self.logger.warning('链接失败，尝试使用后缀.!qB链接')
                    try:
                        os.link('\\\\?\\' + srcpath + val['name'] + '.!qB',
                                '\\\\?\\' + dst + dirname[srcnamelen:] + '\\' + basename)
                    except FileExistsError as _e:
                        self.logger.error(_e)
                    except BaseException as _e:
                        self.logger.error(_e)
                        return False
        return True

    def changerstcategory(self, ptinfo, rtinfo, rtstationname=None, rtcategory=None):
        # 由于各种种子活动状态的不确定性，容易导致移动文件卡死，大文件跨分区的话还容易浪费硬盘性能，目前解决方案为换分类不换目录
        self.qbapi.setAutoManagement([ptinfo['hash'], rtinfo['hash']], False)
        # Reseed的时候主目录是 ---TEST ok
        if rtstationname is not None:
            self.qbapi.setTorrentsCategory(rtinfo['hash'], gl.get_value('config')[rtstationname]['maincategory'])
        elif rtcategory is not None:
            self.qbapi.setTorrentsCategory(rtinfo['hash'], rtcategory)
        self.qbapi.setTorrentsCategory(ptinfo['hash'], self.reseedcategory)

    def post_ressed(self, thash):
        """Return BeautifulSoup Pages
        :url: page url
        :returns: BeautifulSoups
        """
        # self.logger.debug('Get url: ' + url)
        hashstr = ''
        if isinstance(thash, str):
            hashstr = '["' + thash + '"]'
        elif isinstance(thash, list):
            hashstr += '['
            for val in thash:
                hashstr += '"' + val + '",'
            hashstr = hashstr[:-1]
            hashstr += ']'
        data = {
            "hash": hashstr,
            'sha1': hashlib.sha1(hashstr.encode()).hexdigest(),
            "version": "1.5.0",
            "timestamp": time.time(),
            "sign": gl.get_value('config').token
        }
        trytime = 5
        while trytime > 0:
            try:
                req = self._session.post('http://api.iyuu.cn/api/infohash', data=data, timeout=(10, 30))
                return req
            except BaseException as e:
                self.logger.debug(e)
                trytime -= 1
                time.sleep(5)

    def inqueryreseed(self, thash):
        info = self.post_ressed(thash)
        res = []
        if info is None:
            return res
        if info.status_code == 200:
            self.logger.debug(info.text)
            retmsg = {}
            try:
                retmsg = json.loads(info.text)
            except:
                self.logger.error('解析json字符串失败，请联系开发者')
            # if 'success' in retmsg and retmsg['success']:
            #     self.logger.error('未知错误。返回信息为）' + info.text)
            # elif 'success' in retmsg and (not retmsg['success']):
            #     self.logger.error('查询返回失败，错误信息' + retmsg['errmsg'])
            try:
                if retmsg['ret'] != 200:
                    self.logger.error('未知错误。返回信息为）' + info.text)
                elif len(retmsg['data']) != 0:
                    for val in retmsg['data'][thash]['torrent']:
                        # 跳过自己的种
                        if val['info_hash'] == thash:
                            continue
                        if supportsid(val['sid']):
                            res.append({
                                'sid': val['sid'],
                                'tid': val['torrent_id'],
                                'hash': val['info_hash']
                            })
            except:
                self.logger.error('解析服务器返回数据失败')
        else:
            self.logger.error('请求服务器失败！错误状态码:' + str(info.status_code))
        return res

    # 添加被辅种时，查看有没有
    def addpassivereseed(self, thash, rsinfos, content, tid):
        if len(rsinfos) == 0:
            return False
        comlist = [val for val in rsinfos if self.istorrentdlcom(val['hash'])]  # 用来检测种子是否被下载并完成
        if len(comlist) == 0:
            return False
        #  未做 要判断已经辅种失败的种子，就直接下载把，不要辅种了，这种概率很低，可以忽略 未做
        othercatecount = [0, []]
        dlcatecount = [0, []]
        rscatecount = [0, []]
        for val in comlist:
            ct = self.gettorrentcategory(val['hash'])
            if ct in self.dlcategory:
                dlcatecount[0] += 1
                dlcatecount[1].append(val)
            elif ct == self.reseedcategory:
                rscatecount[0] += 1
                rscatecount[1].append(val)
            else:
                othercatecount[0] += 1
                othercatecount[1].append(val)
                break
        ptinfo = None
        if othercatecount[0] > 0:
            ptinfo = othercatecount[1][0]
        elif dlcatecount[0] > 0:
            ptinfo = dlcatecount[1][0]
        else:
            # 讲道理不会运行这里的
            self.logger.warning('运行到奇怪的地方了，赶紧看看是为什么')
            ptinfo = rscatecount[1][0]

        ptinfo = self.qbapi.torrentInfo(ptinfo['hash'])
        dircontent = self.qbapi.torrentFiles(ptinfo['hash'])
        # 防止ReSeed目录里嵌套ReSeed目录
        filterdstpath = ptinfo['save_path']
        filelist = ptinfo['save_path'].split('\\')
        if len(filelist) >= 3:
            pos = 0
            if filelist[-1] == 'ReSeed':
                pos = -1
            elif filelist[-2] == 'ReSeed':
                pos = -2
            elif filelist[-3] == 'ReSeed':
                pos = -3
            if pos != 0:
                filterdstpath = ''
                for i in range(0, len(filelist) + pos):
                    filterdstpath += filelist[i] + '\\'
        self.createhardfiles(ptinfo['save_path'], ptinfo['name'], dircontent, filterdstpath + 'ReSeed\\',
                             thash[:6],
                             get_torrent_name(content))

        if self.qbapi.addNewTorrentByBin(content, paused=True, category=self.reseedcategory, autoTMM=False,
                                         savepath=filterdstpath + 'ReSeed' + '\\' + thash[:6],
                                         upLimit=self.config['uploadspeedlimit'] * 1024 * 1024 / 8):
            self.logger.info('addtorrent  successfully info hash = ' + thash)

            while not self.gettorrentdlstatus(thash):
                time.sleep(5)

            # 删除匹配的tracker,暂时每个种子都判断不管是哪个站点
            self.removematchtracker(thash, 'pttrackertju.tjupt.org')
            self.removematchtracker(thash, 'tracker-campus.tjupt.org')

            self.checktorrenttracker(thash)
            change = 'f'
            if othercatecount[0] > 0:
                change = 'f'
            elif dlcatecount[0] > 0:
                change = 't'
            else:
                change = 'f'
            with open(self.rechecklistname, 'a', encoding='UTF-8')as f:
                f.write(self.config['name'] + ','
                        + tid + ','
                        + 'rs' + ','
                        + thash + ','
                        + '-1,'
                        + change + ','
                        + ptinfo['hash'] + '\n')
            return True
        return False

    def addreseed(self, prhash, rsinfo, content):

        ptinfo = self.qbapi.torrentInfo(prhash)
        dircontent = self.qbapi.torrentFiles(prhash)

        # 防止ReSeed目录里嵌套ReSeed目录
        filterdstpath = ptinfo['save_path']
        filelist = ptinfo['save_path'].split('\\')
        if len(filelist) >= 3:
            pos = 0
            if filelist[-1] == 'ReSeed':
                pos = -1
            elif filelist[-2] == 'ReSeed':
                pos = -2
            elif filelist[-3] == 'ReSeed':
                pos = -3
            if pos != 0:
                filterdstpath = ''
                for i in range(0, len(filelist) + pos):
                    filterdstpath += filelist[i] + '\\'
        if not ptinfo['save_path'].endswith('\\'):
            ptinfo['save_path'] += '\\'
        if not self.createhardfiles(ptinfo['save_path'], ptinfo['name'], dircontent, filterdstpath + 'ReSeed\\',
                                    rsinfo['hash'][:6],
                                    get_torrent_name(content)):
            return False

        if self.qbapi.addNewTorrentByBin(content, paused=True, category=self.reseedcategory, autoTMM=False,
                                         savepath=filterdstpath + 'ReSeed' + '\\' + rsinfo['hash'][:6],
                                         skip_checking=True,
                                         upLimit=self.stationref[getsidname(rsinfo['sid']).lower()].config[
                                                     'uploadspeedlimit'] * 1024 * 1024 / 8):
            self.logger.info('addreseed successfully info hash = ' + rsinfo['hash'])

            # 辅种不需要等待，因为文件本来就存在不需要分配空间
            # 防止磁盘卡死,当磁盘碎片太多或磁盘负载重时此处会卡几到几十分钟
            # while not self.gettorrentdlstatus(rsinfo['hash']):
            #     time.sleep(5)
            time.sleep(2)
            # 删除匹配的tracker,暂时每个种子都判断不管是哪个站点
            # gl.get_value('wechat').send(text='添加种子中断检查tracker断点')
            self.removematchtracker(rsinfo['hash'], 'pttrackertju.tjupt.org')
            self.removematchtracker(rsinfo['hash'], 'tracker-campus.tjupt.org')

            self.checktorrenttracker(rsinfo['hash'])
            ReseedInfoJson().addrstopr(prhash, rsinfo['hash'], getsidname(rsinfo['sid']), rsinfo['tid'], 0)
            with open(self.rechecklistname, 'a', encoding='UTF-8')as f:
                f.write(getsidname(rsinfo['sid']) + ','
                        + str(rsinfo['tid']) + ','
                        + 'rs' + ','
                        + rsinfo['hash'] + ','
                        + str(time.time()) + ','
                        + 'f,'
                        + prhash + '\n')
            return True
        return False

    def recheck(self):
        self.logger.info('检查新添种子状态中...')
        dellist = []
        self.recheckreport.init()
        if os.path.exists(self.rechecklistname):
            allline = []
            with open(self.rechecklistname, 'r', encoding='UTF-8') as f:
                for line in f.readlines():
                    allline.append(line)
            for line in allline:
                self.recheckreport.listlen += 1
                rct = line.strip().split(',')
                self.logger.debug(line)
                if self.rechecktorrent(rct):
                    dellist.append(line)
        newstr = ''
        updatefile = False
        self.logger.info(self.recheckreport)
        if len(dellist) != 0 and os.path.exists(self.rechecklistname):
            with open(self.rechecklistname, 'r', encoding='UTF-8') as f:
                for line in f.readlines():
                    if line in dellist:
                        updatefile = True
                    else:
                        newstr += line
        if updatefile:
            with open(self.rechecklistname, 'w', encoding='UTF-8') as f:
                f.write(newstr)

    def rechecktorrent(self, rct):
        # 下载种子看是否下载完毕
        if rct[2] == 'dl':
            self.recheckreport.dllen += 1
            if self.istorrentexist(rct[3]):
                # 如果在辅种目录说明前面重新辅种了这个种子，从下载状态变换到辅种状态了，跳过即可
                if self.qbapi.torrentInfo(rct[3])['category'] == self.reseedcategory:
                    self.recheckreport.dltors += 1
                    return True
                if self.istorrentdlcom(rct[3]):
                    self.recheckreport.dlcom += 1
                    ReseedInfoJson().addpr(rct[3], rct[0].lower(), rct[1])
                    # testOK
                    inquery = self.inqueryreseed(rct[3])
                    self.addactivereseed(rct[0], rct[1], rct[3], inquery)
                    return True
                else:
                    if self.checktorrenttrakcer(rct[3]):
                        self.logger.info(rct[0] + ':删除' + rct[3] + ',' + rct[1] + '因为种子被站点删除')
                        # gl.get_value('wechat').send(text=rct[0] + ':删除' + ',' + rct[1] + '因为种子被站点删除')
                        self.deletetorrent(rct[3])
                        self.recheckreport.dldel += 1
                        return True
                    if self.checkdltorrenttime(rct):
                        self.recheckreport.dlouttime += 1
                        return True
                    self.recheckreport.dling += 1
                    return False
            else:
                self.recheckreport.dlmiss += 1
                # 种子不见了，可以删掉了
                return True
        # 辅种种子，看是否校验成功
        elif rct[2] == 'rs':
            self.recheckreport.rslen += 1
            if self.istorrentexist(rct[3]):
                res = self.istorrentcheckcom(rct[3])
                if res == 0:
                    # 辅种失败
                    # testOK
                    self.recheckreport.jyfail += 1
                    self.deletetorrent(rct[3], True)
                    ReseedInfoJson().changestatus(rct[6], rct[3], 2)
                    # self.addfailrttopritlist(rct[0], rct[1], rct[3], rct[6])
                    return True
                elif res == 1:
                    # 还未检查完毕
                    # testOK
                    self.recheckreport.jying += 1
                    return False
                elif res == 2:
                    # 是否要交换主从顺序
                    self.recheckreport.jysucc += 1
                    if rct[5] == 't':
                        # testok
                        self.inctpriority2(rct[3], rct[0], rct[1], rct[6])
                    else:
                        # testOK
                        ReseedInfoJson().changestatus(rct[6], rct[3], 1)
                        # self.addrstopritlist(rct[0], rct[1], rct[3], rct[6])
                    self.qbapi.resumeTorrents(rct[3])
                    return True
                elif res == -1:
                    self.logger.warning('返回值为-1，未知错误')
                    return False
            else:
                # 种子不见了，可以删掉了
                self.recheckreport.rsmiss += 1
                return True
        else:
            self.logger.warning('Unknow type')
        return False

    def inctpriority2(self, rehash, rsname, rstid, prihash):
        jsonlist = {}
        # 在则检查主辅，
        with open(self.reseedjsonname, 'r', encoding='UTF-8') as f:
            jsonlist = json.loads(f.read())

        temp = None
        if prihash in jsonlist:
            for idx, val in enumerate(jsonlist[prihash]['rslist']):
                if val['hash'] == rehash:
                    # 正常应该找不到，因为这是新种子，辅种信息里没有这个种子的
                    temp = idx
                    break
            # 若有主，主是否在下载目录，如果是，则转换，如果不是，则此种子已经为辅，不必换
            rsca = self.qbapi.torrentInfo(prihash)
            if rsca['category'] in self.dlcategory or rsca['category'] == self.reseedcategory:
                # 如果是，则转换
                if temp is not None:
                    # 不应该有这个新种的辅种信息
                    self.logger.warning('此处不应该有新种的辅种信息')
                    listinfo = jsonlist[prihash]
                    del jsonlist[prihash]
                    origininfo = listinfo['info']
                    origininfo['status'] = 1
                    rslist = listinfo['rslist']
                    newinfo = {}
                    newinfo['info'] = rslist[temp]
                    del rslist[temp]
                    rslist.append(origininfo)
                    del newinfo['info']['status']
                    newinfo['rslist'] = rslist
                    jsonlist[rehash] = newinfo
                else:
                    listinfo = jsonlist[prihash]
                    del jsonlist[prihash]
                    origininfo = listinfo['info']
                    origininfo['status'] = 1
                    rslist = listinfo['rslist']
                    newinfo = {}
                    newinfo['info'] = {
                        'hash': rehash,
                        'tid': int(rstid) if isinstance(rstid, str) else rstid,
                        'sname': rsname
                    }
                    rslist.append(origininfo)
                    newinfo['rslist'] = rslist
                    jsonlist[rehash] = newinfo
                # 由于各种种子活动状态的不确定性，容易导致移动文件卡死，大文件跨分区的话还容易浪费硬盘性能，目前解决方案为换分类不换目录
                self.changerstcategory(rsca, {'hash': rehash}, rtstationname=rsname)
                with open(self.reseedjsonname, 'w', encoding='UTF-8') as f:
                    f.write(json.dumps(jsonlist))
        else:
            jsonlist[rehash] = {
                'info': {
                    'hash': rehash,
                    # 'sid': getnamesid(prname),
                    'tid': int(rstid) if isinstance(rstid, str) else rstid,
                    'sname': rsname
                },
                'rslist': [{
                    'hash': prihash,
                    # 'sid': getnamesid(prname),
                    'tid': 0,
                    'sname': '',
                    'status': 1
                }]
            }
            self.changerstcategory({'hash': prihash}, {'hash': rehash}, rtstationname=rsname)
            with open(self.reseedjsonname, 'w', encoding='UTF-8') as f:
                f.write(json.dumps(jsonlist))
            # 由于各种种子活动状态的不确定性，容易导致移动文件卡死，大文件跨分区的话还容易浪费硬盘性能，目前解决方案为换分类不换目录

    def addactivereseed(self, prname, prid, prhash, inquery):
        # ReseedInfoJson().addpr(prhash, prname, prid)
        aftercheck = []
        _continue = True
        for val in inquery:
            if getsidname(val['sid']).lower() in self.stationref:
                # 先判断种子在不在，有可能多个站点相同的新种差不多一起下载完，那么把其他站点相同的删掉，变成辅种
                # 正常来说这个种子是不在的，因为下载 前进行过辅种检查，新种才会有这种情况
                # Update 下载前进行过辅种检查，但是服务器可能还没有这个新种的辅种数据，所以会导致没有辅种，当种子下载完成的时候可能就已经入数据库有辅种数据了，就跑到这里来
                # TODO ----test
                if self.istorrentexist(val['hash']):
                    self.logger.warning('辅种种子竟然存在，转为辅种策略.检查看这个种子是否为新种子' + val['hash'])
                    if not self.recheckall_judge(prhash, val):
                        # 当val不是正在下载的种子的时候，说明这个种子之前就存在，把现在这个删掉重新辅种即可,这样可以避免两份空间, 原因可看上面注释
                        self.logger.debug('recheckall_judge')
                        if self.addreseedbyhash(prname, prid, prhash, val):
                            _continue = False
                            break
                else:
                    aftercheck.append(val)
        if _continue:
            for val in aftercheck:
                self.logger.debug('aftercheck')
                rspstream, rspres = self.stationref[getsidname(val['sid']).lower()].getdownloadbypsk(
                    str(val['tid']))
                if rspres:
                    self.addreseed(prhash, val, rspstream.content)
                else:
                    self.logger.warning('种子下载失败，可能被删除了.' + val['hash'])

    def addreseedbyhash(self, prname, prid, prhash, rsinfo):
        newprhash = ReseedInfoJson().findprhashbyhash(rsinfo['hash'])
        if newprhash is None:
            return False
        rspstream, rspres = self.stationref[prname.lower()].getdownloadbypsk(prid)
        if rspres:
            self.deletetorrent(prhash, True)
            time.sleep(1)
            self.addreseed(newprhash, {
                'hash': prhash,
                'tid': prid,
                'sid': getnamesid(prname)
            }, rspstream.content)
        else:
            self.logger.warning('种子下载失败，可能被删除了.' + rsinfo['hash'])
            return False
        return True

    def recheckall(self):
        self.logger.info('检查全种子可辅种信息...')
        reseedlist = {}
        reseedalllist = []
        if os.path.exists(self.reseedjsonname):
            with open(self.reseedjsonname, 'r', encoding='UTF-8')as f:
                reseedlist = json.loads(f.read())
        for key, value in reseedlist.items():
            reseedalllist.append(key)
            for val in value['rslist']:
                reseedalllist.append(val['hash'])
        qblist = self.qbapi.torrentsInfo(filter='completed')
        for val in qblist:
            if val['category'] == 'Reseed' or val['category'] in gl.get_value(
                    'config').qbtignore:  # 不收集辅种分类和忽略分类，否则可能会导致在辅种中再辅种的问题
                continue
            if val['state'] == 'missingFiles':  # 跳过丢失文件的种子
                continue
            if not val['hash'] in reseedalllist:
                reseedlist[val['hash']] = {
                    'info': {
                        'hash': val['hash'],
                        'tid': 0,
                        'sanme': ''
                    },
                    'rslist': []
                }
        # 提取全部主种的hash
        prialllist = []
        for key, value in reseedlist.items():
            prialllist.append(key)

        reslist = self.inqueryreseeds(prialllist)
        # self.logger.info('可辅种大小：' + str(len(reslist)))
        self.recheckallreport.init()
        self.recheckallreport.resnum = len(reslist)
        self.recheckallreport.inquerynum = len(prialllist)

        for key, value in reslist.items():
            self.logger.info('检查主种.' + key)
            if len(value['torrent']) == 0:
                self.recheckallreport.nofznum += 1
            else:
                self.recheckallreport.availablenum += 1
            for val in value['torrent']:
                self.recheckallreport.rsnum += 1
                self.logger.info('检查辅种.' + val['hash'] + ',tid:' + str(val['tid']) + ',sid:' + str(val['sid']))
                if val['hash'] in reseedalllist:
                    self.recheckallreport.yfznum += 1
                    continue
                if self.istorrentexist(val['hash']):
                    self.recheckallreport.fzingnum += 1
                    if not self.istorrentdlcom(val['hash']):
                        self.recheckall_judge(key, val)
                else:
                    self.recheckallreport.newfznum += 1
                    rspstream, rspres = self.stationref[getsidname(val['sid'])].getdownloadbypsk(str(val['tid']))
                    if rspres:
                        # 种子下载有问题的时候name空的，有一定几率会误判种子下载成功了，和网络状况有关
                        # 另一种情况是，误判了种子下载成功，其实此种子被删除了，获取到的是html的内容
                        if get_torrent_name(rspstream.content) is None:
                            self.recheckallreport.failnum += 1
                            continue
                        self.recheckallreport.succnum += 1
                        self.addreseed(key, val, rspstream.content)
                    else:
                        self.recheckallreport.failnum += 1
                        self.logger.warning('种子下载失败，可能被删除了.' + val['hash'])
        self.logger.info(self.recheckallreport)

    def inqueryreseeds(self, thashs):
        info = self.post_ressed(thashs)
        res = {}
        if info is None:
            self.logger.error('连接辅种服务器失败')
            return {}
        if info.status_code == 200:
            # self.logger.debug(info.text)
            # if info.text != 'null':

            retmsg = {}
            try:
                retmsg = json.loads(info.text)
            except:
                self.logger.error('解析json字符串失败，请联系开发者')
            # if 'success' in retmsg and retmsg['success']:
            #     self.logger.error('未知错误。返回信息为）' + info.text)
            # elif 'success' in retmsg and (not retmsg['success']):
            #     self.logger.error('查询返回失败，错误信息' + retmsg['errmsg'])
            try:
                if retmsg['ret'] != 200:
                    self.logger.error('未知错误。返回信息为）' + info.text)
                elif len(retmsg['data']) != 0:
                    for key, value in retmsg['data'].items():
                        res[key] = {'torrent': []}
                        for idx, val in enumerate(value['torrent']):
                            if not supportsid(val['sid']):
                                continue
                            if val['info_hash'] == key:
                                continue
                            res[key]['torrent'].append({
                                'hash': val['info_hash'],
                                'tid': val['torrent_id'],
                                'sid': val['sid']
                            })
            except:
                self.logger.error('解析服务器返回数据失败')
            # else:
            #     self.logger.debug('服务器返回null，未查询到辅种数据')
        else:
            self.logger.error('请求服务器失败！错误状态码:' + str(info.status_code))
        return res

    def recheckall_judge(self, prihash, rsinfo):
        thash = rsinfo['hash']
        newstr = ''
        updatefile = False
        if os.path.exists(self.rechecklistname):
            with open(self.rechecklistname, 'r', encoding='UTF-8') as f:
                for line in f.readlines():
                    rct = line.strip().split(',')
                    # 正在辅种的跳过即可
                    if rct[3] == thash and rct[2] == 'rs':
                        return True
                    if rct[3] == thash and rct[2] == 'dl':
                        self.deletetorrent(thash, True)
                        updatefile = True
                    else:
                        newstr += line
        if updatefile:
            # 必须先写入，否则回合addreseed里的写入冲突，导致被覆盖
            with open(self.rechecklistname, 'w', encoding='UTF-8') as f:
                f.write(newstr)
            # 在if里，只有dl情况，并且没有下载完才需要删除并辅种，校验中的不应该进入这里
            # 在recheck里，可能会存在多站点相同新种同时下载完毕，导致互相辅种创建硬链接浪费空间，用这个函数重新辅种
            rspstream, rspres = self.stationref[getsidname(rsinfo['sid'])].getdownloadbypsk(rsinfo['tid'])
            if rspres:
                self.addreseed(prihash, rsinfo, rspstream.content)
            else:
                self.logger.warning('种子下载失败，可能被删除了.' + rsinfo['hash'])

            return True
        return False

    def checkdltorrenttime(self, dline):
        ret = False
        if float(dline[4]) > 0:
            if float(dline[4]) - time.time() > 1800:
                ret = False
            else:
                self.deletetorrent(dline[3])
                self.logger.info(dline[0] + ':删除' + dline[3] + ',' + dline[1] + '.因为没有在免费时间内下载完毕.')
                ret = True
        if float(dline[4]) == -1:
            # 避免种子下载时间太久浪费资源，使用简单的算法
            tinfo = self.qbapi.torrentInfo(dline[3])
            # 算500k每秒 需要的下载时间秒
            dllmtime = tinfo['size'] / (500 * 1024)
            # 再预留一天的时间 但如果现在有下载速度大于100k则不删除
            if time.time() > tinfo['added_on'] + 86400 + dllmtime and tinfo['dlspeed'] < (100 * 1024):
                self.deletetorrent(dline[3])
                self.logger.info(dline[0] + ':删除' + dline[3] + ',' + dline[1] + '.因为超出最大下载时间.')
                ret = True
        return ret

    def checkemptydir(self):
        self.logger.info('检查空文件夹中...')
        category = self.qbapi.category()
        pathlist = []
        for k, v in category.items():
            if k in gl.get_value('config').qbtignore:  # 跳过忽略分类
                continue
            if v['savePath'] != '':
                pathlist.append(v['savePath'].replace('/', '\\'))
        qbconfig = self.qbapi.getApplicationPreferences()
        if qbconfig['save_path'] != '':
            pathlist.append(qbconfig['save_path'])
        pathlist2 = []
        for val in set(pathlist):
            if not val.endswith('\\'):
                val = val + '\\'
            pathlist2.append(val + 'ReSeed')
        dirinfo = {
            'emptynum': 0,
            'notemptynum': 0,
            'filesnum': 0,
            'emptylist': []
        }
        for val in pathlist2:
            for k, v in getemptydirlist(val).items():
                dirinfo[k] += v
        dirinfo['qbrsnum'] = len(self.qbapi.torrentsInfo(category=self.reseedcategory))
        self.logger.info(checkDirReport(dirinfo))
        deletedir(dirinfo['emptylist'])

    def checktorrenttrakcer(self, thash):
        # ----test
        info = self.qbapi.torrentTrackers(thash)
        for val in info:
            if val['status'] == 0:
                continue
            if any(s in val['msg'] for s in ['not registered', '被删除', 'banned']):
                return True
        return False

    def checkprttracker(self):
        self.logger.info('检查种子tracker状态中...')
        if not os.path.exists(self.reseedjsonname):
            return
        jsonlist = {}
        with open(self.reseedjsonname, encoding='utf-8')as f:
            jsonlist = json.loads(f.read())
        for k, v in jsonlist.items():
            if not self.checktorrenttrakcer(k):
                continue
            if len(v['rslist']) == 0:
                self.logger.info('删除主种' + k + '.因为种子被站点删除，并且没有辅种信息')
                self.deletetorrent(k)
                continue
            rsinfo = None
            for val in v['rslist']:
                if val['sname'] != '' and val['status'] != 2 and not self.checktorrenttrakcer(val['hash']):
                    rsinfo = val
                    break
            if rsinfo is None:
                # gl.get_value('wechat').send(text='程序断点提醒---json种子被删除测试')
                self.logger.info('删除主种' + k + '.因为种子被站点删除，并且辅种信息都是校验失败或都已被站点删除')
                self.deletetorrent(k)
                continue
            self.logger.info('交换主种' + k + '与辅种' + rsinfo['hash'] + '次序，因为主种被站点删除')
            self.inctpriority3(rsinfo, k)

    def inctpriority3(self, rsinfo, prihash):
        jsonlist = {}
        # 在则检查主辅，
        with open(self.reseedjsonname, 'r', encoding='UTF-8') as f:
            jsonlist = json.loads(f.read())
        temp = None
        if prihash in jsonlist:
            for idx, val in enumerate(jsonlist[prihash]['rslist']):
                if val['hash'] == rsinfo['hash']:
                    temp = idx
                    break
        if temp is not None:
            listinfo = jsonlist[prihash]
            del jsonlist[prihash]
            origininfo = listinfo['info']
            origininfo['status'] = 1
            rslist = listinfo['rslist']
            newinfo = {}
            newinfo['info'] = rslist[temp]
            del rslist[temp]
            rslist.append(origininfo)
            del newinfo['info']['status']
            newinfo['rslist'] = rslist
            jsonlist[rsinfo['hash']] = newinfo

            self.changerstcategory({'hash': prihash}, rsinfo, rtstationname=rsinfo['sname'])
            with open(self.reseedjsonname, 'w', encoding='UTF-8') as f:
                f.write(json.dumps(jsonlist))

    def checkalltorrentexist(self):
        self.logger.info('检查种子存在状态中...')
        if not os.path.exists(self.reseedjsonname):
            return
        jsonlist = {}
        with open(self.reseedjsonname, encoding='utf-8')as f:
            jsonlist = json.loads(f.read())
        info = self.qbapi.torrentsInfo()
        info = {val['hash']: val for val in info}
        delprhash = []
        delrsidx = {}
        for k, v in jsonlist.items():
            if k in info:
                delrsidx[k] = []
                for idx, rs in enumerate(v['rslist']):
                    if rs['status'] == 2:
                        continue
                    if rs['hash'] not in info:
                        self.logger.info('辅种.{}.不见了删除辅种信息,主种为.{}'.format(rs['hash'], k))
                        delrsidx[k].append(rs)
                if len(delrsidx[k]) == 0:
                    del delrsidx[k]
            else:
                self.logger.info('主种.{}.不见了删除主辅种信息'.format(k))
                delprhash.append(k)
                dellist = [k]
                for rs in v['rslist']:
                    if rs['status'] == 2:
                        continue
                    dellist.append(rs['hash'])
                self.qbapi.torrentsDelete(dellist, True)
        if len(delrsidx) != 0 or len(delprhash) != 0:
            for val in delprhash:
                del jsonlist[val]
            for k, v in delrsidx.items():
                for delv in v:
                    jsonlist[k]['rslist'].remove(delv)
            with open(self.reseedjsonname, 'w', encoding='utf-8')as f:
                f.write(json.dumps(jsonlist))

    def changechecklistrs(self, thash):
        newstr = ''
        updatefile = False
        if os.path.exists(self.rechecklistname):
            with open(self.rechecklistname, 'r', encoding='UTF-8') as f:
                tempdic = {}
                for line in f.readlines():
                    rct = line.strip().split(',')
                    if rct[3] == thash and rct[2] == 'rs':
                        rct[5] = 't'
                        updatefile = True
                        newstr += ','.join(rct) + '\n'
                        tempdic[rct[6]] = rct[3]
                    else:
                        if rct[2] == 'rs' and rct[6] in tempdic:
                            if rct[5] == 'f':
                                rct[6] = tempdic[rct[6]]
                            else:
                                rct[6] = tempdic[rct[6]]
                                tempdic[rct[6]] = rct[3]
                            newstr += ','.join(rct) + '\n'
                        else:
                            newstr += line
        if updatefile:
            with open(self.rechecklistname, 'w', encoding='UTF-8') as f:
                f.write(newstr)
            return True
        return False
