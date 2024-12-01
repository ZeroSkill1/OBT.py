from argparse import ArgumentParser
from enum import IntEnum
from typing import IO
import struct
import sys
import os
import re

ENTNAME_PATTERN = re.compile('^(?:.*)*?\\.entry(\\d+)(\\.bin(?:\\.clz77)?)$')

class OBTError(Exception):
    def __init__(self, msg):
        super().__init__(f"OBT Error: {msg}")

class InvalidOBTFileError(OBTError):
    def __init__(self, msg: str):
        super().__init__(f"Invalid OBT File: {msg}")

class OBTFileMode(IntEnum):
    OBT_None = -1,
    OBT_Read = 0,
    OBT_Write = 1

class OBTEntry:
    offset: int
    size: int
    is_compressed: int
    loaded: bool = False
    raw_entry: bytes

    def __init__(self):
        self.offset = -1
        self.size = -1
        self.is_compressed = -1
        self.loaded = False
        self.raw_entry = None

    def load(self, offset, size, is_compressed):
        self.offset = offset
        self.size = size
        self.is_compressed = is_compressed
        self.loaded = True

    def frombytes(self, entry: bytes):
        if self.loaded:
            raise OBTError("Cannot overwrite a loaded entry")

        self.size = len(entry)
        self.raw_entry = entry

    def __str__(self):
        if self.loaded:
            return f"{self.__class__.__name__} at offset {hex(self.offset)} and size {hex(self.size)} ({self.size}), compressed: {self.is_compressed == 1}"
        else:
            return f"Uninitialized {self.__class__.__name__}"


class OBT:
    entries: dict[int, OBTEntry]
    fp: IO
    filename: str
    total_size: int
    entry_offset: int
    mode: OBTFileMode

    def __init__(self, filename: str):
        self.entries = {}
        self.fp = None
        self.filename = filename
        self.total_size = 0
        self.entry_offset = 0
        self.mode = OBTFileMode.OBT_None

    def init_write(self, overwrite: bool = False):
        if self.mode != OBTFileMode.OBT_None:
            raise OBTError("File is already opened")

        if os.path.isfile(self.filename) and not overwrite:
            raise OBTError(f"Will not overwrite {self.filename} unless explicitly enabled")

        self.fp = open(self.filename, "wb+")
        self.mode = OBTFileMode.OBT_Write

    def load(self):
        if self.mode != OBTFileMode.OBT_None:
            raise OBTError("File is already opened")

        if not os.path.isfile(self.filename):
            raise FileNotFoundError(self.filename)

        raw_fsiz = os.path.getsize(self.filename)

        if raw_fsiz < 4:
            raise InvalidOBTFileError("Could not read header size")

        self.fp = open(self.filename, "rb")
        self.fp.seek(0)
        hdr_size = int.from_bytes(self.fp.read(4), "little")

        if raw_fsiz < hdr_size:
            raise InvalidOBTFileError("Could not read header")

        self.total_size += hdr_size

        n_entries = hdr_size // 0xC

        for i in range(n_entries):
            self.fp.seek(i * 0xC)
            entry_offset, entry_size, entry_is_compressed = struct.unpack("<III", self.fp.read(0xC))
            if entry_is_compressed not in [0, 1]:
                raise OBTError("Unknown compression method")
            self.entries[i] = OBTEntry()
            self.entries[i].load(entry_offset, entry_size, entry_is_compressed)
            self.total_size += entry_size

        if raw_fsiz < self.total_size:
            raise InvalidOBTFileError("Not enough data in file")

        self.mode = OBTFileMode.OBT_Read

    def add_entry(self, entry: bytes, compressed: bool):
        if self.mode != OBTFileMode.OBT_Write:
            raise OBTError("OBT has not been opened for writing")

        obt_entry = OBTEntry()
        obt_entry.frombytes(entry)
        obt_entry.is_compressed = compressed

        self.entries[self.entry_offset] = obt_entry
        self.entry_offset += 1

    def finalize_write(self):
        if self.mode != OBTFileMode.OBT_Write:
            raise OBTError("OBT has not been opened for writing")

        if not len(self.entries):
            raise OBTError("No entries to write")

        sorted_entry_ids = sorted(self.entries.keys())
        header_size = len(self.entries) * 0xC

        self.fp.seek(0)

        cur_off = header_size

        # write the header

        for i in range(len(sorted_entry_ids)):
            ent = self.entries[i]
            header_entry = struct.pack("<III", cur_off, ent.size, ent.is_compressed)
            self.fp.write(header_entry)
            cur_off += ent.size

        # write the entries

        for i in range(len(sorted_entry_ids)):
            self.fp.write(self.entries[i].raw_entry)

    def export_entry(self, entry_idx: int) -> bytes:
        if self.mode != OBTFileMode.OBT_Read:
            raise OBTError("File is not opened")
        elif entry_idx not in self.entries:
            raise OBTEntry(f"Entry {entry_idx} not found in file")

        entry = self.entries[entry_idx]

        self.fp.seek(entry.offset)

        return self.fp.read(entry.size)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tb):
        if self.fp != None and not self.fp.closed:
            self.fp.close()

        return exc_type is None

    def __str__(self) -> str:
        if self.filename:
            return f"{self.__class__.__name__} {self.filename} with {len(self.entries)} entries, total size: {self.total_size}"
        else:
            return f"Uninitialized {self.__class__.__name__}"

argp = ArgumentParser(description="Extracts/Creates OBT files.")
subp = argp.add_subparsers(title="Available commands", dest="action_name")

extractp = subp.add_parser("extract", help="Extract an OBT file.")
extractp.add_argument("filename", type=str, help="The OBT file to extract.")
extractp.add_argument("outdir", type=str, nargs="?", help="The directory to output the extracted sections to. Defaults to the current directory.", default=os.curdir)

createp = subp.add_parser("create", help="Create an OBT file from files extracted using the \"extract\" command.")
createp.add_argument("-o", "--output", type=str, help="Output OBT file path.", dest="output", required=True)
createp.add_argument("entries", type=str, nargs="+", help="The section files to repack into the OBT format. Note that only the file name format of the \"extract\" command is accepted.")
createp.add_argument("-w", "--overwrite", action="store_true", help="Whether or not to overwrite the output file if it already exists.", required=False, default=False, dest="overwrite")

args = argp.parse_args()
if not args.action_name:
    argp.print_usage()

if args.action_name == "extract":
    if not os.path.isfile(args.filename):
        sys.exit(f"{args.filename}: file not found")

    if not os.path.isdir(args.outdir):
        os.mkdir(args.outdir)

    obtname = os.path.basename(args.filename)

    try:
        with OBT(args.filename) as obt_file:
            obt_file.load()
            print(obt_file)
            for idx, entry in obt_file.entries.items():
                print(entry)
                outpath = os.path.join(args.outdir, f"{obtname}.entry{idx}.bin")
                if entry.is_compressed:
                    outpath += ".clz77"

                with open(outpath, "wb") as ent:
                    ent.write(obt_file.export_entry(idx))

            print(f"Successfully extracted {len(obt_file.entries)} entries from {args.filename}.")
    except Exception as e:
        print(f"Could not load {args.filename}:")
        print(e)
elif args.action_name == "create":
    if os.path.isfile(args.output) and not args.overwrite:
        sys.exit(f"Will not overwrite {args.output}. Pass -w/--overwrite to bypass.")

    if any([x for x in args.entries if not os.path.isfile(x)]):
        sys.exit("One or more of the specified entry files do not exist.")

    meta: list[tuple[int, bool, str]] = []
    idxtable: list[int] = []

    for entryname in args.entries:
        mat = ENTNAME_PATTERN.match(entryname)
        if not mat:
            sys.exit(f"Invalid entry file name: {entryname}")
        entryidx, extension = mat.groups()
        idx = int(entryidx)
        if idx in idxtable:
            sys.exit(f"Error: duplicate entry with index {idx}")
        meta.append((idx, extension == ".bin.clz77", entryname))
        idxtable.append(idx)

    meta = sorted(meta, key=lambda m: m[0])

    with OBT(args.output) as obt:
        obt.init_write(args.overwrite)

        for idx, compressed, filename in meta:
            with open(filename, "rb") as entryfile:
                obt.add_entry(entryfile.read(), compressed)

        obt.finalize_write()

    print(f"Successfully repacked {len(meta)} entries into {args.output}.")
