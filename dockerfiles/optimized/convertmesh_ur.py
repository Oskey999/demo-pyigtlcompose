import trimesh, glob, os, sys, subprocess

files = glob.glob('/opt/ros/humble/share/ur_description/**/*.dae', recursive=True)
print(f'Converting {len(files)} ur_description .dae mesh files...')
ok, fail = 0, 0
for dae in files:
    try:
        stl_path = dae.replace('.dae', '.stl')
        mesh = trimesh.load(dae, force='mesh', skip_materials=True)
        mesh.export(stl_path, file_type='stl')
        os.remove(dae)
        print(f'  OK: {os.path.basename(stl_path)}')
        ok += 1
    except Exception as e:
        print(f'  FAIL: {os.path.basename(dae)}: {e}')
        fail += 1

# Patch all URDF/xacro references from .dae to .stl
for ext in ['*.urdf', '*.xacro', '*.urdf.xacro']:
    for f in glob.glob(f'/opt/ros/humble/share/ur_description/**/{ext}', recursive=True):
        with open(f, 'r') as fh:
            content = fh.read()
        if '.dae' in content:
            with open(f, 'w') as fh:
                fh.write(content.replace('.dae', '.stl'))
            print(f'  Patched URDF: {os.path.basename(f)}')

print(f'Done: {ok} converted, {fail} failed')
sys.exit(1 if fail == len(files) else 0)