# Parses the CTAB (constant table) comment block of D3D9 shader bytecode: prints name, register set, register, count.
import struct, sys, glob, os
SETS = {0: 'b', 1: 'i', 2: 'c', 3: 's'}
def ctab(path):
    d = open(path, 'rb').read()
    ver = struct.unpack_from('<I', d, 0)[0]
    i = 4; out = []
    while i + 4 <= len(d):
        tok = struct.unpack_from('<I', d, i)[0]
        if tok & 0xFFFF == 0xFFFE:                       # comment
            n = (tok >> 16) & 0x7FFF
            body = d[i + 4:i + 4 + n * 4]
            if body[:4] == b'CTAB':
                t = body[4:]
                size, creator, version, ncon, coff, flags, target = struct.unpack_from('<7I', t, 0)
                for k in range(ncon):
                    nameo, rset, ridx, rcnt, res, tinfo, defv = struct.unpack_from('<IHHHHII', t, coff + k * 20)
                    name = t[nameo:t.index(b'\0', nameo)].decode('latin1')
                    out.append((SETS.get(rset, '?') + str(ridx), rcnt, name))
                return ver, out
            i += 4 + n * 4
        else:
            break
    return ver, out
if __name__ == '__main__':
    for f in sorted(glob.glob(sys.argv[1] if len(sys.argv) > 1 else r'C:\Users\HENRIQUE\Tools\captures\shaders\*.bin')):
        ver, cs = ctab(f)
        print(os.path.basename(f), hex(ver), len(cs), ' | '.join('%s[%d]=%s' % c for c in sorted(cs, key=lambda c: (c[0][0], int(c[0][1:])))))
