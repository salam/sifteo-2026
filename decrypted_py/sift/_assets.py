import os, re, types

def _file_list(dir_path, pattern=None):
    listing = os.listdir(dir_path)
    return [n for n in listing if \
            os.path.isfile(os.path.join(dir_path, n)) and \
            ((pattern is None) or re.search(pattern, n))]

class _AssetSet(object):
    
    def __init__(self, path, asset_class, pattern=None):
        self.dict = dict()
        self.base_dict = dict()
        self.list = list()
        if path is not None and os.path.exists(path):           
            for i,filename in enumerate(_file_list(path, pattern)):
                self.insert( path, filename, i, asset_class )                   

    def insert(self, path, filename, index, asset_class):
        asset_path = os.path.join(path, filename)
        asset = asset_class(asset_path, index)
        self.dict[asset.filename] = asset
        self.base_dict[asset.base_filename] = asset
        self.list.append(asset)
    
    def __getitem__(self, item):       
        try:           
            if type(item) == types.IntType:
                return self.list[item]
            else:               
                return self.dict[item]
        except KeyError, IndexError:
            raise AssetError("Asset not found: %s" % str(item))
            
            
            
    def __len__(self):
        return len(self.list)
            
    def lookup_basename(self, name):
        try:
            return self.base_dict[name]
        except KeyError:
            raise AssetError("Asset not found: %s" % str(name))
        
    def empty(self):
        return len(self.list) is 0
        
    def __iter__(self):
        return iter(self.list)
            
class _Asset(object):
    
    def __init__(self, path, index):
        self.filename = os.path.split(path)[-1]
        self.base_filename = os.path.splitext(self.filename)[0]
        self.path = path
        self.index = index
        
        
class AssetError(Exception):

    def __init__(self, msg):
        Exception.__init__(self, msg)
    
