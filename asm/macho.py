"""Mach-O 64-bit executable writer for macOS ARM64"""

import struct


def write_macho(output_file: str, machine_code: list[int], labels: dict[str, int],
                base_address: int = 0x100000000, entry_point: str = '_start') -> None:
    """
    Write a minimal Mach-O 64-bit executable containing a single __TEXT/__text
    section and an LC_MAIN load command.

    The ``base_address`` must match the value used during assembly so that
    label addresses are consistent with the LC_SEGMENT_64 vmaddr.
    """
    if entry_point not in labels:
        raise ValueError(f"Entry point '{entry_point}' not found in labels")

    text_size = len(machine_code) * 4
    text_addr = base_address  # vmaddr of __TEXT segment
    entry_addr = labels[entry_point]
    text_fileoff = 0x4000  # conventional page-aligned offset for __text

    with open(output_file, 'wb') as f:
        # ---- Mach-O header (32 bytes) ----
        f.write(struct.pack('<I', 0xFEEDFACF))  # magic: MH_MAGIC_64
        f.write(struct.pack('<I', 0x0100000C))  # cputype: CPU_TYPE_ARM64
        f.write(struct.pack('<I', 0x00000000))  # cpusubtype: CPU_SUBTYPE_ARM64_ALL
        f.write(struct.pack('<I', 0x00000002))  # filetype: MH_EXECUTE
        f.write(struct.pack('<I', 3))           # ncmds
        f.write(struct.pack('<I', 0))           # sizeofcmds (filled in later)
        f.write(struct.pack('<I', 0x00200085))  # flags
        f.write(struct.pack('<I', 0))           # reserved

        header_end = f.tell()   # = 32
        load_cmd_start = header_end

        # ---- LC_SEGMENT_64: __PAGEZERO (72 bytes) ----
        f.write(struct.pack('<I', 0x19))                            # cmd: LC_SEGMENT_64
        f.write(struct.pack('<I', 72))                              # cmdsize
        f.write(b'__PAGEZERO\x00\x00\x00\x00\x00\x00')            # segname (16 bytes)
        f.write(struct.pack('<Q', 0))                               # vmaddr
        f.write(struct.pack('<Q', 0x100000000))                     # vmsize
        f.write(struct.pack('<Q', 0))                               # fileoff
        f.write(struct.pack('<Q', 0))                               # filesize
        f.write(struct.pack('<I', 0))                               # maxprot
        f.write(struct.pack('<I', 0))                               # initprot
        f.write(struct.pack('<I', 0))                               # nsects
        f.write(struct.pack('<I', 0))                               # flags

        # ---- LC_SEGMENT_64: __TEXT (segment header 64 bytes + section header 80 bytes = 144... ----
        # Standard cmdsize for one section: 72 (segment) + 80 (section) = 152 but  ...
        # struct section_64 = 16+16+8+8+4+4+4+4+4+4+4 = 80 bytes
        # struct segment_command_64 = 4+4+16+8+8+8+8+4+4+4+4 = 72 bytes
        text_seg_cmdsize = 72 + 80  # = 152
        vmsize = max(text_size, 0x4000)  # at least one page

        f.write(struct.pack('<I', 0x19))                            # cmd: LC_SEGMENT_64
        f.write(struct.pack('<I', text_seg_cmdsize))                # cmdsize
        f.write(b'__TEXT\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00')  # segname (16 bytes)
        f.write(struct.pack('<Q', text_addr))                       # vmaddr
        f.write(struct.pack('<Q', vmsize))                          # vmsize
        f.write(struct.pack('<Q', 0))                               # fileoff
        f.write(struct.pack('<Q', text_fileoff + text_size))        # filesize
        f.write(struct.pack('<I', 0x7))                             # maxprot (rwx)
        f.write(struct.pack('<I', 0x5))                             # initprot (r-x)
        f.write(struct.pack('<I', 1))                               # nsects
        f.write(struct.pack('<I', 0))                               # flags

        # __text section header (80 bytes)
        f.write(b'__text\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00')   # sectname (16 bytes)
        f.write(b'__TEXT\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00')   # segname (16 bytes)
        f.write(struct.pack('<Q', text_addr))                          # addr
        f.write(struct.pack('<Q', text_size))                          # size
        f.write(struct.pack('<I', text_fileoff))                       # offset
        f.write(struct.pack('<I', 2))                                  # align (2^2 = 4)
        f.write(struct.pack('<I', 0))                                  # reloff
        f.write(struct.pack('<I', 0))                                  # nreloc
        f.write(struct.pack('<I', 0x80000400))                         # flags (PURE_INSTRUCTIONS)
        f.write(struct.pack('<I', 0))                                  # reserved1
        f.write(struct.pack('<I', 0))                                  # reserved2
        f.write(struct.pack('<I', 0))                                  # reserved3

        # ---- LC_MAIN (24 bytes) ----
        f.write(struct.pack('<I', 0x80000028))                      # cmd: LC_MAIN
        f.write(struct.pack('<I', 24))                              # cmdsize
        f.write(struct.pack('<Q', entry_addr - text_addr))          # entryoff (from segment start)
        f.write(struct.pack('<Q', 0))                               # stacksize

        # ---- Patch sizeofcmds at offset 20 in the header ----
        load_cmd_end = f.tell()
        sizeofcmds = load_cmd_end - load_cmd_start
        f.seek(20)
        f.write(struct.pack('<I', sizeofcmds))

        # ---- Write machine code at text_fileoff ----
        f.seek(text_fileoff)
        for instr in machine_code:
            f.write(struct.pack('<I', instr))

    print(f"Generated: {output_file}  ({text_size} bytes, entry 0x{entry_addr:x})")
