import json
import os

from jsmin import jsmin


class Config(object):
    """read config"""

    def __getitem__(self, key):
        if key.upper() == 'BYR':
            return self.byrconfig
        elif key.upper() == 'TJU':
            return self.tjuconfig
        elif key.upper() == 'PTER':
            return self.pterconfig
        elif key.upper() == 'MTEAM':
            return self.mteamconfig
        elif key.upper() == 'PTHOME':
            return self.pthomeconfig
        elif key.upper() == 'FRDS':
            return self.frdsconfig
        elif key.upper() == 'LEMONHD':
            return self.lemonhdconfig
        elif key.upper() == 'TTG':
            return self.ttgconfig
        elif key.upper() == 'SOULVOICE':
            return self.soulvoiceconfig
        elif key.upper() == 'ALL':
            return {
                'BYR': self.byrconfig,
                'TJU': self.tjuconfig,
                'PTER': self.pterconfig,
                'MTEAM': self.mteamconfig,
                'PTHOME': self.pthomeconfig,
                'FRDS': self.frdsconfig,
                'TTG': self.ttgconfig,
                'SOULVOICE': self.soulvoiceconfig,
                'LEMONHD': self.lemonhdconfig,
            }
        else:
            return {}

    def __init__(self):
        self.reseedconfig = {
            'switch': True,
            # TODO token为空时报错退出
            'token': ''
        }
        self.byrconfig = {
            'switch': False,
            'onlyattendance': False,
            'name': 'BYR',
            'passkey': '',
            'maincategory': '',
            'subcategory': [],
            'capacity': 0,
            'capacityuint': 'TB',
            'capacitynum': 0,
            'intervaltime': 30,
            'keeptorrenttime': 168,
            'uploadspeedlimit': 0,
            'urlparam': '',
            'root': 'https://bt.byr.cn/'
        }
        self.tjuconfig = {
            'switch': False,
            'onlyattendance': False,
            'name': 'TJU',
            'passkey': '',
            'maincategory': '',
            'subcategory': [],
            'capacity': 0,
            'capacityuint': 'TB',
            'capacitynum': 0,
            'intervaltime': 30,
            'keeptorrenttime': 168,
            'uploadspeedlimit': 0,
            'urlparam': '',
            'root': 'https://www.tjupt.org/'
        }
        self.pterconfig = {
            'switch': False,
            'onlyattendance': False,
            'name': 'PTER',
            'passkey': '',
            'maincategory': '',
            'subcategory': [],
            'capacity': 0,
            'capacityuint': 'TB',
            'capacitynum': 0,
            'intervaltime': 30,
            'keeptorrenttime': 168,
            'uploadspeedlimit': 0,
            'urlparam': '',
            'root': 'https://pterclub.com/'
        }
        self.mteamconfig = {
            'switch': False,
            'onlyattendance': False,
            'name': 'MTeam',
            'passkey': '',
            'maincategory': '',
            'subcategory': [],
            'capacity': 0,
            'capacityuint': 'TB',
            'capacitynum': 0,
            'intervaltime': 30,
            'keeptorrenttime': 168,
            'uploadspeedlimit': 0,
            'urlparam': 'ipv6=1&https=1&',
            'root': 'https://pt.m-team.cc/'
        }
        self.pthomeconfig = {
            'switch': False,
            'onlyattendance': False,
            'name': 'PTHOME',
            'passkey': '',
            'maincategory': '',
            'subcategory': [],
            'capacity': 0,
            'capacityuint': 'TB',
            'capacitynum': 0,
            'intervaltime': 30,
            'keeptorrenttime': 168,
            'uploadspeedlimit': 0,
            'urlparam': '',
            'root': 'https://www.pthome.net/'
        }
        self.frdsconfig = {
            'switch': False,
            'onlyattendance': False,
            'name': 'FRDS',
            'passkey': '',
            'level': 0,
            'maincategory': '',
            'subcategory': [],
            'capacity': 0,
            'capacityuint': 'TB',
            'capacitynum': 0,
            'intervaltime': 30,
            'keeptorrenttime': 168,
            'uploadspeedlimit': 0,
            'urlparam': '',
            'root': 'https://pt.keepfrds.com/'
        }
        self.ttgconfig = {
            'switch': False,
            'onlyattendance': False,
            'name': 'TTG',
            'passkey': '',
            'level': 0,
            'maincategory': '',
            'subcategory': [],
            'capacity': 0,
            'capacityuint': 'TB',
            'capacitynum': 0,
            'intervaltime': 30,
            'keeptorrenttime': 168,
            'uploadspeedlimit': 0,
            'urlparam': '',
            'root': 'https://totheglory.im/'
        }
        self.lemonhdconfig = {
            'switch': False,
            'onlyattendance': False,
            'name': 'TTG',
            'passkey': '',
            'level': 0,
            'maincategory': '',
            'subcategory': [],
            'capacity': 0,
            'capacityuint': 'TB',
            'capacitynum': 0,
            'intervaltime': 30,
            'keeptorrenttime': 168,
            'uploadspeedlimit': 0,
            'urlparam': 'https=1&',
            'root': 'https://lemonhd.org/'
        }
        self.soulvoiceconfig = {
            'switch': False,
            'onlyattendance': False,
            'name': 'SoulVoice',
            'passkey': '',
            'level': 0,
            'maincategory': '',
            'subcategory': [],
            'capacity': 0,
            'capacityuint': 'TB',
            'capacitynum': 0,
            'intervaltime': 30,
            'keeptorrenttime': 168,
            'uploadspeedlimit': 0,
            'urlparam': 'https=1&',
            'root': 'https://pt.soulvoice.club/'
        }
        self.qbtconfig = {
            'url': '',
            'path': '',
            'username': '',
            'password': '',
            'ignore': []
        }
        if os.path.exists('config.json'):
            f = open('config.json', 'r', encoding='utf-8')
            text = jsmin(f.read())
            # text = f.read()
            f.close()
            paras = json.loads(text)
            self.readqbtconfig(paras)
            self.readlogconfig(paras)
            self.readbyrconfig(paras)
            self.readtjuconfig(paras)
            self.readpterconfig(paras)
            self.readmteamconfig(paras)
            self.readpthomeconfig(paras)
            self.readfrdsconfig(paras)
            self.readttgconfig(paras)
            self.readlemonhdconfig(paras)
            self.readsoulvoiceconfig(paras)
            self.readreseedconfig(paras)
        else:
            self._logsavetime = 7
            self._loglevel = 'info'

    def transcapacity(self, config):
        if config['capacityuint'] == 'GB':
            config['capacity'] = config['capacitynum']
        elif config['capacityuint'] == 'TB':
            config['capacity'] = config['capacitynum'] * 1024
        elif config['capacityuint'] == 'MB':
            config['capacity'] = config['capacitynum'] / 1024
        else:
            config['capacity'] = 0

    def readbyrconfig(self, param):
        if 'BYR' in param:
            paras = param['BYR']
            self.readcommonconfig(paras, self.byrconfig)
            # To add custom config here

    def readtjuconfig(self, param):
        if 'TJU' in param:
            paras = param['TJU']
            self.readcommonconfig(paras, self.tjuconfig)
            # To add custom config here

    def readpterconfig(self, param):
        if 'PTER' in param:
            paras = param['PTER']
            self.readcommonconfig(paras, self.pterconfig)
            # To add custom config here

    def readmteamconfig(self, param):
        if 'MTEAM' in param:
            paras = param['MTEAM']
            self.readcommonconfig(paras, self.mteamconfig)
            # To add custom config here

    def readpthomeconfig(self, param):
        if 'PTHOME' in param:
            paras = param['PTHOME']
            self.readcommonconfig(paras, self.pthomeconfig)
            # To add custom config here

    def readfrdsconfig(self, param):
        if 'FRDS' in param:
            paras = param['FRDS']
            self.readcommonconfig(paras, self.frdsconfig)
            # To add custom config here

    def readttgconfig(self, param):
        if 'TTG' in param:
            paras = param['TTG']
            self.readcommonconfig(paras, self.ttgconfig)
            # To add custom config here

    def readlemonhdconfig(self, param):
        if 'LEMONHD' in param:
            paras = param['LEMONHD']
            self.readcommonconfig(paras, self.lemonhdconfig)
            # To add custom config here

    def readsoulvoiceconfig(self, param):
        if 'SoulVoice' in param:
            paras = param['SoulVoice']
            self.readcommonconfig(paras, self.soulvoiceconfig)
            # To add custom config here

    def readcommonconfig(self, paras, pt_config):
        if 'switch' in paras:
            pt_config['switch'] = paras['switch']
        if 'onlyAttendance' in paras:
            pt_config['onlyattendance'] = paras['onlyAttendance']
        if 'IntervalTime' in paras:
            if pt_config['onlyattendance']:
                # 只签到模式，间隔6小时访问一次
                pt_config['intervaltime'] = 60 * 60 * 6
            else:
                pt_config['intervaltime'] = paras['IntervalTime'] * 60
        if 'CapacityNum' in paras:
            pt_config['capacitynum'] = paras['CapacityNum'] if paras['CapacityNum'] > -1 else 10485760
        if 'CapacityUint' in paras:
            pt_config['capacityuint'] = paras['CapacityUint'].upper() \
                if paras['CapacityUint'].upper() in ['GB', 'TB'] else 'GB'
        if 'MainCategory' in paras:
            pt_config['maincategory'] = paras['MainCategory'][0] if len(paras['MainCategory'][:1]) > 0 else ''
            pt_config['subcategory'] = paras['MainCategory'][1:]
            pt_config['subcategory'] = list(set(pt_config['subcategory']))
        if 'KeepTorrentTime' in paras:
            pt_config['keeptorrenttime'] = paras['KeepTorrentTime'] if paras['KeepTorrentTime'] >= 0 else 0
        if 'passkey' in paras:
            pt_config['passkey'] = paras['passkey']
        if 'UploadSpeedLimit' in paras:
            pt_config['uploadspeedlimit'] = paras['UploadSpeedLimit']
        # 转换磁盘容量
        self.transcapacity(pt_config)

    def readlogconfig(self, para):
        if 'log' in para:
            paras = para['log']
            if 'LogLevel' in paras:
                self._loglevel = paras['LogLevel'].lower()
                self._loglevel = self._loglevel if self._loglevel in ['info', 'debug'] else 'info'
            else:
                self._loglevel = 'info'
            if 'LogSaveTime' in paras:
                self._logsavetime = paras['LogSaveTime']
            else:
                self._logsavetime = 7
        else:
            self._loglevel = 'info'
            self._logsavetime = 7

    def readqbtconfig(self, para):
        if 'QBitTorrent' in para:
            paras = para['QBitTorrent']
            if 'path' in paras:
                self.qbtconfig['path'] = paras['path']
            else:
                self.qbtconfig['path'] = ''
            if 'url' in paras:
                if not (paras['url'].startswith('http://') or paras['url'].startswith('https://')):
                    paras['url'] = 'http://' + paras['url']
                self.qbtconfig['url'] = paras['url'][:-1] if paras['url'].endswith('/') else paras['url']
            else:
                self.qbtconfig['url'] = ''
            if 'username' in paras:
                self.qbtconfig['username'] = paras['username']
            else:
                self.qbtconfig['username'] = ''
            if 'password' in paras:
                self.qbtconfig['password'] = paras['password']
            else:
                self.qbtconfig['password'] = ''
            if 'ignore' in paras:
                self.qbtconfig['ignore'] = paras['ignore']
            else:
                self.qbtconfig['ignore'] = []

    def readreseedconfig(self, para):
        if 'ReSeed' in para:
            paras = para['ReSeed']
            if 'switch' in paras:
                self.reseedconfig['switch'] = paras['switch']
            else:
                self.reseedconfig['switch'] = False
            if 'token' in paras:
                self.reseedconfig['token'] = paras['token']
            else:
                self.reseedconfig['token'] = ""

    def getnameconfig(self):
        return {
            'BYR': self.byrconfig,
            'TJU': self.tjuconfig,
            'PTER': self.pterconfig,
            'MTEAM': self.mteamconfig,
            'PTHOME': self.pthomeconfig,
            'FRDS': self.frdsconfig,
            'TTG': self.ttgconfig,
            'LEMONHD': self.lemonhdconfig,
            'SOULVOICE': self.soulvoiceconfig,
            'RESEED': self.reseedconfig
        }

    def switch(self, name):
        return self.getnameconfig()[name.upper()]['switch']

    def name(self, name):
        return self.getnameconfig()[name.upper()]['name']

    def keeptorrenttime(self, name):
        return self.getnameconfig()[name.upper()]['keeptorrenttime']

    def maincategory(self, name):
        return self.getnameconfig()[name.upper()]['maincategory']

    def subcategory(self, name):
        return self.getnameconfig()[name.upper()]['subcategory']

    def capacity(self, name):
        return self.getnameconfig()[name.upper()]['capacity']

    def intervaltime(self, name):
        return self.getnameconfig()[name.upper()]['intervaltime']

    def passkey(self, name):
        return self.getnameconfig()[name.upper()]['passkey']

    def uploadspeedlimit(self, name):
        return self.getnameconfig()[name.upper()]['uploadspeedlimit']

    @property
    def qbtaddr(self):
        return self.qbtconfig['url']

    @property
    def token(self):
        return self.reseedconfig['token']

    @property
    def qbtpath(self):
        return self.qbtconfig['path']

    @property
    def qbtusername(self):
        return self.qbtconfig['username']

    @property
    def qbtpassword(self):
        return self.qbtconfig['password']

    @property
    def qbtignore(self):
        return self.qbtconfig['ignore']

    @property
    def loglevel(self):
        return self._loglevel

    @property
    def logsavetime(self):
        return self._logsavetime
