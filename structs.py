from nbt import nbt
from copy import deepcopy
import ujson as json
import os
import sys


class MC_struct(object):
    """Only to read file"""
    def __init__(self, filename):
        self.length = 0
        self.height = 0
        self.width = 0
        self.ids = []
        self.metadata = []
        self.block_data = []
        self.filename = filename
        self.is_new = False

    def load_from_file(self):
        fnbt = nbt.NBTFile(self.filename, "rb")
        self.set_sizes(fnbt)
        self.set_data_old(fnbt)

    @staticmethod
    def get_val_by_file(file, key):
        try:
            return file[key].value
        except KeyError:
            return None

    def set_sizes(self, fnbt):
        self.length = MC_struct.get_val_by_file(fnbt, "Length")
        self.height = MC_struct.get_val_by_file(fnbt, "Height")
        self.width = MC_struct.get_val_by_file(fnbt, "Width")

    def set_data_old(self, fnbt):
        self.ids = MC_struct.get_val_by_file(fnbt, "Blocks")
        self.metadata = MC_struct.get_val_by_file(fnbt, "Data")
        if self.ids is None and self.metadata is None:
            self.set_data_new(fnbt)

    def set_data_new(self, fnbt):
        self.is_new = True
        self.block_data = MC_struct.get_val_by_file(fnbt, "BlockData")
        self.palette = {}
        with open(resource_path("convert_data_new.json"), "r") as f:
            data = json.load(f)
        data = self.load_custom(data)
        for tag in fnbt["Palette"].tags:
            self.palette[tag.value] = BlockNew(tag.name)
            self.palette[tag.value].convert(data)

    def get_block_at(self, x=0, y=0, z=0, ind=None):
        if ind:
            i = ind
        else:
            i = x + (z + y * self.length) * self.width
        try:
            return Block(self.ids[i], self.metadata[i])
        except TypeError:
            data = self.block_data[i]
            return self.palette[data], data

    def set_block_data(self):
        bstring = self.block_data[::]
        self.block_data = []
        i = 0
        while i < len(bstring):
            value = 0
            varint_length = 0
            while True:
                value |= (bstring[i] & 127) << (varint_length * 7)
                varint_length += 1
                if (bstring[i] & 128) != 128:
                    i += 1
                    break
                i += 1
            self.block_data.append(value)

    def load_custom(self, data):
        new_data = deepcopy(data)
        try:
            with open("convert_data_custom.json") as f:
                addict = json.load(f)
            if "blocks" in addict.keys():
                blocks = addict["blocks"]
            if "datas" in addict.keys():
                datas = addict["datas"]
            for key in blocks.keys():
                new_data["blocks"][key] = blocks[key]
            for key in datas.keys():
                new_data["datas"][key] = datas[key]
            return new_data
        except Exception:
            return data


class VS_struct(object):
    """Only to write struct"""
    def __init__(self, filename, version="1.16.5"):
        self.filename = filename
        self.version = version
        self.size_x = 0
        self.size_y = 0
        self.size_z = 0
        self.block_codes = {}
        self.indices = []
        self.block_ids = []
        self.replace_mode = 2

    def convert_from(self, struct):
        self.size_x = struct.width
        self.size_y = struct.height
        self.size_z = struct.length
        if struct.is_new:
            for i in self.convert_from_newest(struct):
                yield i
        else:
            i_max = 0
            errors = set()
            with open(resource_path("convert_data.json"), "r") as f:
                data = json.load(f)
            for y in range(self.size_y):
                for z in range(self.size_z):
                    for x in range(self.size_x):
                        ind = x | ((z | (y << 10)) << 10)
                        block = struct.get_block_at(x, y, z)
                        block.convert(data)
                        if block.is_incorrect():
                            errors.add(str(f"{block.mc_id}:{block.mc_meta}"))
                            continue
                        if block.is_air():
                            continue
                        if not block.vs_id in self.block_codes.values():
                            self.block_codes[i_max] = block.vs_id
                            i_max += 1
                        i = get_key(self.block_codes, block.vs_id)
                        self.block_ids.append(i)
                        self.indices.append(ind)
                yield f"app.layer {y + 1}/{self.size_y} app.complete ({(y + 1) * 100 // (self.size_y)}%)"
            yield "app.finalizing"
            self.write_to_file()
            self.write_log_err(errors)


    def convert_from_newest(self, struct):
        yield "app.start"
        struct.set_block_data()
        # struct.load_custom()
        errors = set()
        i = 1
        maxi = len(struct.palette)
        for block, block_id in zip(struct.palette.values(), struct.palette):
            if block.is_incorrect():
                errors.add(str(f"{block.mc_id}:{block.mc_meta}"))
            self.block_codes[block_id] = block.vs_id
            yield f"app.block {i}/{maxi} app.complete ({i * 100 // maxi}%)"
            i += 1
        for y in range(self.size_y):
            for z in range(self.size_z):
                for x in range(self.size_x):
                    ind = x | ((z | (y << 10)) << 10)
                    block, data = struct.get_block_at(x, y, z)
                    if block.is_air():
                        continue
                    self.block_ids.append(data)
                    self.indices.append(ind)
            yield f"app.layer {y + 1}/{self.size_y} app.complete ({(y + 1) * 100 // (self.size_y)}%)"
        yield "app.finalizing"
        temp = self.block_codes.copy()
        for key in temp.keys():
            if self.block_codes[key] == "air":
                self.block_codes.pop(key)
        self.write_to_file()
        self.write_log_err(errors)

    def write_to_file(self):
        data = {}
        data["Version"] = self.version
        data["SizeX"] = self.size_x
        data["SizeY"] = self.size_y
        data["SizeZ"] = self.size_z
        data["BlockCodes"] = self.block_codes
        data["BlockIds"] = self.block_ids
        data["Indices"] = self.indices
        data["ReplaceMode"] = self.replace_mode
        with open(self.filename, "w") as out:
            json.dump(data, out)

    def write_log_err(self, data):
        with open("errors.log", "w") as file:
            for elem in data:
                file.write(elem + "\n")


class Block(object):
    """Block object"""
    def __init__(self, mc_id=0, mc_meta=0):
        self.mc_id = str(mc_id)
        self.mc_meta = str(mc_meta)
        self.vs_id = ""
        self.err = False

    def convert(self, data):
        try:
            metainfo = data[self.mc_id]
            if "*" in metainfo:
                self.vs_id = metainfo["*"]
            else:
                self.vs_id = metainfo[self.mc_meta]
        except KeyError:
            self.vs_id = "air"
            self.err = True

    def is_air(self):
        return self.mc_id == "0" or self.vs_id == "air" or self.mc_id == "air"

    def is_incorrect(self):
        return self.err


class BlockNew(Block):
    """BlockNew object"""
    def __init__(self, name):
        super(BlockNew, self).__init__()
        temp = name.split("[")
        temp[0] = temp[0].split(":")[1]
        self.mc_id = temp[0]
        if len(temp) == 1:
            self.mc_meta = {}
        else:
            temp[1] = temp[1][:-1]
            temp = [i.split("=") for i in temp[1].split(",")]
            self.mc_meta = {elem[0]: elem[1] for elem in temp}

    def convert(self, data):
        try:
            self.vs_id = data["blocks"][self.mc_id]
            datas = data["datas"]
            for key in self.mc_meta:
                if key in datas.keys():
                    temp = datas[key]
                    if self.mc_meta[key] in temp.keys():
                        value = temp[self.mc_meta[key]]
                        tag = key.upper()
                        self.vs_id = self.vs_id.replace(tag, value)
            if "*" in self.vs_id:
                raise KeyError
        except KeyError:
            self.vs_id = "air"
            self.err = True


def get_key(data, value):
    for key, val in data.items():
        if val == value:
            return key


def resource_path(relative):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative)
    return os.path.join(relative)
