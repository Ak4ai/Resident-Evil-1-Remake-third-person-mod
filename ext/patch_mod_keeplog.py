# Keep the previous run's log (modlog_prev.txt) so a crash can be diagnosed after the game is restarted.
p = r'C:\Users\HENRIQUE\Tools\re1mod\mod\mod.c'
s = open(p, 'rb').read().decode('latin1')
old = '    g_mlog = fopen(lp, "w");\r\n    M_("mod_init (deferred)\\n");'
assert old in s, 'anchor'
new = ('    { char pv[MAX_PATH]; snprintf(pv, sizeof pv, "%s\\\\modlog_prev.txt", dir); MoveFileExA(lp, pv, MOVEFILE_REPLACE_EXISTING); } /* keep previous run */\r\n' + old)
s = s.replace(old, new, 1)
open(p, 'wb').write(s.encode('latin1'))
print('patched')
