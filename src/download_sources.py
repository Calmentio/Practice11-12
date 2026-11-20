"""Download two *real* sources; never synthesize demographic input here."""
from __future__ import annotations
import os, sys, shutil, subprocess
from pathlib import Path
import requests
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT/'data'/'raw'
RAR_URL = 'https://tochnostdatasets.fra1.digitaloceanspaces.com/Catalog/Rosstat/data_regions_collection_102_v1.0/section_01.rar'
GEO_URL = 'https://raw.githubusercontent.com/imsha/russia_geojson_regions_2021/main/ru.json'

def fetch(url: str, path: Path):
    if path.exists() and path.stat().st_size > 1000:
        print('Already present:', path); return
    print('Downloading', url)
    tmp = path.with_suffix(path.suffix+'.part')
    with requests.get(url, stream=True, timeout=90, headers={'User-Agent':'ADiMO-edu-project/1.0'}) as resp:
        resp.raise_for_status()
        with tmp.open('wb') as f:
            for block in resp.iter_content(chunk_size=1024*1024):
                if block: f.write(block)
    tmp.replace(path)
    print('Saved', path, path.stat().st_size)

def find_7zip():
    for name in ('7z','7zz','7za','unar','bsdtar'):
        f = shutil.which(name)
        if f: return f
    if os.name == 'nt':
        for p in ('C:/Program Files/7-Zip/7z.exe','C:/Program Files (x86)/7-Zip/7z.exe', 'C:/Program Files/WinRAR/UnRAR.exe'):
            if Path(p).exists(): return p
    return None

def main():
    RAW.mkdir(parents=True,exist_ok=True)
    try:
        fetch(GEO_URL, RAW/'regions_2021.geojson')
    except Exception as e:
        print('GEOMETRY DOWNLOAD ERROR:', e)
        print('Manually save', GEO_URL, 'as data/raw/regions_2021.geojson')
        return 1
    if list(RAW.rglob('*.csv')):
        print('CSV files already found; skip archive download.')
        return 0
    try: fetch(RAR_URL, RAW/'section_01.rar')
    except Exception as e:
        print('STATISTICS DOWNLOAD ERROR:', e)
        print('Open', RAR_URL, 'and extract CSV files into data/raw/')
        return 1
    seven = find_7zip()
    if seven:
        if Path(seven).name.lower().startswith('unar'):
            command = [seven,'-o',str(RAW),str(RAW/'section_01.rar')]
        elif Path(seven).name.lower().startswith('bsdtar'):
            command = [seven,'-xf',str(RAW/'section_01.rar'),'-C',str(RAW)]
        elif 'unrar' in Path(seven).name.lower():
            command = [seven,'x','-o+',str(RAW/'section_01.rar'),str(RAW)]
        else:
            command = [seven,'x','-y',f'-o{RAW}',str(RAW/'section_01.rar')]
        subprocess.run(command,check=True)
    else:
        try:
            import rarfile
            with rarfile.RarFile(RAW/'section_01.rar') as rf: rf.extractall(RAW)
        except Exception as e:
            print('RAR extractor unavailable:', e)
            print('Install 7-Zip or manually extract the section_01.rar contents to data/raw/')
            return 1
    files = list(RAW.rglob('*.csv'))
    print('Found CSV files:',len(files))
    if not files:
        print('No CSV files extracted; inspect archive manually.')
        return 1
    return 0
if __name__=='__main__': sys.exit(main())
