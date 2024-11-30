# OBT.py

This script can extract and repack OBT files which are common in the Parascientific Escape series of games and possibly others on the Nintendo 3DS.

The format is extremely simple and therefore I'll just document it here in this README.

# OBT File format

OBT is essentially a general-purpose data container for (optionally LZ77-compressed) data entries. It can be thought of as a zip file without filenames (though much simpler). OBT files begin with an arbitrarily sized header, which is just an array of metadata structures containing information about the data entries they define.

All integers in the header are in little endian format.

Entry metadata struct:

| Offset | Size |         Description                                            |
|--------|------|----------------------------------------------------------------|
|   0x0  |   4  | Absolute offset of entry data                                  |
|   0x4  |   4  | Size of entry                                                  |
|   0x8  |   4  | Whether or not compression is enabled (0 = disabled, 1 = LZ77) |

The header consists entirely of these metadata structs written directly after one another without any padding in between. Nothing directly defines the size of the header, so the only way to determine the header size is to take the absolute entry offset of the first metadata entry and use that as the header size, because the data for the first entry is found immediately after the header, or in other words, at the offset defined in the first metadata entry.

Each entry spans exactly from `Absolute offset of entry data` to `Absolute offset of entry data + Size of entry` in the OBT file.

The total number of entries in an OBT file can be calculated as follows:

```
number of total entries (n) = absolute offset of entry data for first metadata struct / 12 (size of meta struct)
```

To read the file, one must first determine the header size as mentioned above, then calculate the number of entries (n). Using the metadata, each entry can be extracted individually.

# Script usage

The script uses nothing but the builtin python libraries.

Parameters enclosed in square brackets `[]` are optioinal.

- Extracting an OBT file:

  `python3 OBT.py extract myfile.obt [output directory]`

  If the output directory is omitted, entries will be extracted into the current directory.

- Repacking extracted entries into an OBT file:

  `python3 OBT.py create -o myrepack.obt myfile.obt.entry0.bin myfile.obt.entry1.bin (etc. ) [-w/--overwrite]`

  You must specify `-w/--overwrite` if the output file already exists.

# Naming scheme

The script adheres to a strict file naming scheme to prevent unexpected behavior with the games using this file format. Since no file names are used in OBT files, presumably the only way to differentiate entries is through their order in the OBT file.

For example, extracting an OBT file called `myfile.obt` using the script will produce the following entry files:

- `myfile.obt.entry0.bin`
- `myfile.obt.entry1.bin.clz77`

Files ending in `.bin` are not compressed.

Files ending in `.bin.clz77` are compressed using LZ77. Tools like [3dstool](https://github.com/dnasdw/3dstool) and [Kuriimu2](https://github.com/FanTranslatorsInternational/Kuriimu2) can uncompress these files.

When modifying game assets using this script, make sure that you **do not** change the file names of the extracted entries. Keeping the file names consistent ensures the correct entries will be repacked in the same order they originally were in.

**Please make sure to also recompress entries if you modify compressed ones! The script will set the compression flag for all entry files ending in `.bin.clz77`. If you don't do this, the game will most likely crash.**
