'''
(*)~---------------------------------------------------------------------------
Pupil - eye tracking platform
Copyright (C) 2012-2018 Pupil Labs

Distributed under the terms of the GNU
Lesser General Public License (LGPL v3.0).
See COPYING and COPYING.LESSER for license details.
---------------------------------------------------------------------------~(*)
'''

import pickle
import msgpack
import os
import numpy as np
import traceback as tb
import logging
from glob import iglob
logger = logging.getLogger(__name__)
UnpicklingError = pickle.UnpicklingError


class Persistent_Dict(dict):
    """a dict class that uses pickle to save inself to file"""
    def __init__(self, file_path, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.file_path = os.path.expanduser(file_path)
        try:
            self.update(**load_object(self.file_path,allow_legacy=False))
        except IOError:
            logger.debug("Session settings file '{}' not found. Will make new one on exit.".format(self.file_path))
        except:  # KeyError, EOFError
            logger.warning("Session settings file '{}'could not be read. Will overwrite on exit.".format(self.file_path))
            logger.debug(tb.format_exc())

    def save(self):
        d = {}
        d.update(self)
        save_object(d, self.file_path)

    def close(self):
        self.save()


def _load_object_legacy(file_path):
    file_path = os.path.expanduser(file_path)
    with open(file_path, 'rb') as fh:
        data = pickle.load(fh, raw=True)
    return data


def load_object(file_path,allow_legacy=True):
    import gc
    file_path = os.path.expanduser(file_path)
    with open(file_path, 'rb') as fh:
        try:
            gc.disable()  # speeds deserialization up.
            data = msgpack.unpack(fh, raw=False)
        except Exception as e:
            if not allow_legacy:
                raise e
            else:
                logger.info('{} has a deprecated format: Will be updated on save'.format(file_path))
                data = _load_object_legacy(file_path)
        finally:
            gc.enable()
    return data


def save_object(object_, file_path):

    def ndarrray_to_list(o, _warned=[False]): # Use a mutlable default arg to hold a fn interal temp var.
        if isinstance(o, np.ndarray):
            if not _warned[0]:
                logger.warning("numpy array will be serialized as list. Invoked at:\n"+''.join(tb.format_stack()))
                _warned[0] = True
            return o.tolist()
        return o

    file_path = os.path.expanduser(file_path)
    with open(file_path, 'wb') as fh:
        msgpack.pack(object_, fh, use_bin_type=True,default=ndarrray_to_list)

def load_pupil_data_file(file_path):
    """
    load Pupil data file, output data is dicts of toplevel topic with tuples of data inside.
    Each datum is a immutable dict that is unpacked on access.
    """
    with open(file_path,"rb") as fh:
        pupil_data = {}
        for topic, payload in msgpack.Unpacker(fh, raw=False, use_list=False):
            topic = topic.split(".")[0]
            if topic not in pupil_data:
                pupil_data[topic] = []
            pupil_data[topic].append(Serialized_Dict(payload=payload))
    return pupil_data

def save_pupil_data_file(file_path,data):
    """
    example implementation of data saver, this should really be done incrementally during
    recording and based on the serialized the message on the IPC.
    data is a list of datums each a dict with at least a 'topic' field.
    """
    packer = msgpack.Packer(use_bin_type=True)
    with open("file_path","wb") as fb:
        for datum in data:
            payload = (datum['topic'],msgpack.dumps(datum,use_bin_type=True))
            fb.write(packer.pack(payload))

def next_export_sub_dir(root_export_dir):
    # match any sub directories or files a three digit pattern
    pattern = os.path.join(root_export_dir, '[0-9][0-9][0-9]')
    existing_subs = sorted(iglob(pattern))
    try:
        latest = os.path.split(existing_subs[-1])[-1]
        next_sub_dir = '{:03d}'.format(int(latest) + 1)
    except IndexError:
        next_sub_dir = '000'

    return os.path.join(root_export_dir, next_sub_dir)


class Serialized_Dict():

    cache_len = 100

    class Empty(object):
        def purge_cache(self):
            pass

    _cache_ref = [Empty()]*cache_len

    #an Immutable dict for dics nested inside this dict.
    class FrozenDict(dict):

        def __setitem__(self, key, value):
            raise NotImplementedError('Invalid operation')

        def clear(self):
            raise NotImplementedError()

        def update(self, *args, **kwargs):
            raise NotImplementedError()

    def __init__(self, mapping=None,payload=None):
        if type(mapping) is dict:
            self._ser_data = msgpack.dumps(mapping,use_bin_type=True)
        elif type(payload) is bytes:
            self._ser_data = payload
        else:
            raise Exception("neither mapping nor payload is supplied or wrong format.")
        self._data = None


    def _object_hook(self,obj):
        if type(obj) is dict:
            return self.FrozenDict(obj)

    def _deser(self):
        if not self._data:
            self._data = msgpack.loads(self._ser_data,raw=False,use_list=False, object_hook=self._object_hook)
            self._cache_ref.pop(0).purge_cache()
            self._cache_ref.append(self)

    def purge_cache(self):
        self._data = None

    def __setitem__(self, key, item):
        raise NotImplementedError()
        self._data[key] = item

    def __getitem__(self, key):
        self._deser()
        return self._data[key]

    def __repr__(self):
        self._deser()
        return repr(self._data)

    def __len__(self):
        self._deser()
        return len(self._data)

    def __delitem__(self, key):
        raise NotImplementedError()
        self._deser()
        del self._data[key]

    def get(self,key,default):
        try:
            return self['key']
        except KeyError:
            return default

    def clear(self):
        raise NotImplementedError()
        return self._data.clear()

    def copy(self):
        self._deser()
        return self._data.copy()

    def has_key(self, k):
        self._deser()
        return k in self._data

    def update(self, *args, **kwargs):
        raise NotImplementedError()
        self._deser()
        return self._data.update(*args, **kwargs)

    def keys(self):
        self._deser()
        return self._data.keys()

    def values(self):
        self._deser()
        return self._data.values()

    def items(self):
        self._deser()
        return self._data.items()

    def pop(self, *args):
        raise NotImplementedError()
        return self._data.pop(*args)

    def __cmp__(self, dict_):
        self._deser()
        return self.__cmp__(self._data, dict_)

    def __contains__(self, item):
        self._deser()
        return item in self._data

    def __iter__(self):
        self._deser()
        return iter(self._data)

    def __unicode__(self):
        self._deser()
        return unicode(repr(self._data))




def bench_save():
    import time
    # in recorder
    start = time.time()
    data = []
    inters= 200*60*60 # 1h recording
    dummy_datum = {'topic': 'pupil', 'circle_3d': {'center': [0.0, -0.0, 0.0], 'normal': [0.0, -0.0, 0.0], 'radius': 0.0}, 'confidence': 0.0, 'timestamp': 0.9351908409998941, 'diameter_3d': 0.0, 'ellipse': {'center': [96.0, 96.0], 'axes': [0.0, 0.0], 'angle': 90.0}, 'norm_pos': [0.5, 0.5], 'diameter': 0.0, 'sphere': {'center': [-2.2063483765091934, 0.0836648916925231, 48.13110450930929], 'radius': 12.0}, 'projected_sphere': {'center': [67.57896110256269, 97.07772787219814], 'axes': [309.15558975219403, 309.15558975219403], 'angle': 90.0}, 'model_confidence': 1.0, 'model_id': 1, 'model_birth_timestamp': 640.773183, 'theta': 0, 'phi': 0, 'method': '3d c++', 'id': 0}

    with open("test","wb") as fb:
        packer = msgpack.Packer(use_bin_type=True)
        for x in range(inters):
            a = "pupil",msgpack.dumps(dummy_datum,use_bin_type=True)
            b = "pupil",msgpack.dumps(dummy_datum,use_bin_type=True)
            c = "gaze",msgpack.dumps(dummy_datum,use_bin_type=True)
            aa = "aa",msgpack.dumps({"test":{"nested":True}},use_bin_type=True)
            fb.write(packer.pack(a))
            fb.write(packer.pack(b))
            fb.write(packer.pack(c))
            fb.write(packer.pack(aa))
    print("generated and saved in %s"%(time.time()-start))


def bench_load():

    import time
    start = time.time()
    pupil_data = load_pupil_data_file("test")
    print(pupil_data.keys())
    print("loaded in %s"%(time.time()-start))



if __name__ == '__main__':
    import sys
    # d = load_object("/Users/mkassner/Downloads/000/pupil_data")["gaze_positions"]
    # size = len(d)
    # print(size)
    # # del d
    # l = []
    # for p in range(size):
    #     l.append(Serialized_Dict(d[p]))
    #     l[-1]['timestamp']
    # del(d)
    # print(size)
    # print("slfrf")
    # from time import sleep
    # sleep(10)
    bench_save()
    from time import sleep
    # sleep(3)
    bench_load()


