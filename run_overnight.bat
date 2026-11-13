@echo off
set BL="C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
cd /d C:\Users\HENRIQUE\Tools\re1mod
echo [1] UV v2 %date% %time%
%BL% -b blend\r105_work.blend --python ext\make_lm_uv_v2.py > logs_uv.txt 2>&1
echo [2] bake base lareira velas arandelas %date% %time%
%BL% -b blend\r105_lm_v2.blend --python ext\bake_lm_layers.py -- base lareira velas arandelas > logs_bake.txt 2>&1
echo [3] despeckle dilate png %date% %time%
python ext\despeckle_lm.py base lareira velas arandelas > logs_post.txt 2>&1
python ext\dilate_lm.py >> logs_post.txt 2>&1
python ext\lm_layers_to_png.py >> logs_post.txt 2>&1
echo [4] export %date% %time%
%BL% -b blend\r105_lm_v2.blend --python ext\export_1c_groups_lm_blender.py > logs_exp.txt 2>&1
python ext\export_3c_rms4.py >> logs_exp.txt 2>&1
echo FIM %date% %time%
