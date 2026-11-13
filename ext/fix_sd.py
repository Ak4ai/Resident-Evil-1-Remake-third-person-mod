p = r'C:\Users\HENRIQUE\Tools\re1mod\mod\mod.c'
s = open(p, 'rb').read().decode('latin1')
i = s.index('M_("shaderdump %d')
j = s.index('g_shdDump); } }', i)
s = s[:i] + 'M_("shaderdump %d\\n", ' + s[j:]
open(p, 'wb').write(s.encode('latin1'))
print(s[i - 40:i + 60])
