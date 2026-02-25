import trimesh, glob, os, sys 
files = glob.glob('/root/ros2_ws/install/**/*.dae', recursive=True) 
print(f'Converting {len(files)} .dae mesh files to STL format...') 
ok, fail = 0, 0 
for dae in files: 
    try: 
        mesh = trimesh.load(dae, force='mesh', skip_materials=True) 
        stl_bytes = mesh.export(file_type='stl') 
        with open(dae, 'wb') as f: 
            f.write(stl_bytes) 
        print(f'  OK: {os.path.basename(dae)}') 
        ok += 1 
    except Exception as e: 
        print(f'  WARNING: Failed {os.path.basename(dae)}: {e}') 
        fail += 1 
print(f'Done: {ok} converted, {fail} failed') 
sys.exit(1 if fail == len(files) else 0)