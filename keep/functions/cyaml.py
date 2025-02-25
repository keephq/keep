import yaml
from yaml import *


def safe_load(stream):
    return yaml.load(stream, Loader=yaml.CSafeLoader)

def dump(data, stream=None, Dumper=None, **kwds):
    Dumper = Dumper or yaml.CDumper
    # TODO: preserve quotes of strings e.g. query: "SELECT ..." should stay as is
    return yaml.dump(data, stream, Dumper=Dumper, **kwds)

def add_representer(data_type, representer, Dumper=None):
    Dumper = Dumper or yaml.CDumper
    Dumper.add_representer(data_type, representer)
