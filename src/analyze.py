"""Team 3, seminars 11-12. Reproducible regional demographic spatial clustering.

Real mode NEVER substitutes synthetic data for missing 2021 observations.
Demo mode uses explicitly fictional polygons and numbers only for smoke testing.
"""
from __future__ import annotations
import argparse, json, re, sys, time, logging, hashlib
from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import box
import networkx as nx
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler, RobustScaler
from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.metrics import silhouette_score, davies_bouldin_score, adjusted_rand_score
from sklearn.metrics.pairwise import haversine_distances
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components
from scipy.stats import skew

ROOT=Path(__file__).resolve().parents[1]
FEATURES={
    'urban_share':('01030000','Доля городского населения, %'),
    'natural_change':('01140000','Естественный прирост, ‰'),
    'migration_change':('01200000','Миграционный прирост, ‰'),
    'fertility':('01150000','Суммарный коэффициент рождаемости')
}
FN=list(FEATURES)
COLORS=['#32C9BC','#F1B65C','#779DF6','#CB83CE','#E87588','#9DD476']
logging.basicConfig(level=logging.INFO,format='%(asctime)s | %(levelname)s | %(message)s',datefmt='%H:%M:%S')

SPECIAL={'республика алтай':'алтай республика','алтай':'алтай республика','алтайский край':'алтай край',
    'саха якутия':'саха','якутия':'саха','республика саха':'саха',
    'чувашская республика чувашия':'чувашия','чувашская республика':'чувашия','чувашия':'чувашия',
    'республика северная осетия алания':'северная осетия алания','северная осетия алания':'северная осетия алания',
    'ненецкий автономный округ':'ненецкий','ханты мансийский автономный округ югра':'ханты мансийский',
    'ханты мансийский автономный округ':'ханты мансийский',
    'ямало ненецкий автономный округ':'ямало ненецкий',
    'еврейская автономная область':'еврейская',
    'республика крым':'крым','город севастополь':'севастополь',
    'город федерального значения москва':'москва',
    'город федерального значения санкт петербург':'санкт петербург',
    'кемеровская область кузбасс':'кемеровская',
    'удмуртская республика':'удмуртия','республика удмуртия':'удмуртия',
    'республика мордовия':'мордовия', 'республика татарстан':'татарстан'}

def norm(s):
    s=str(s).lower().replace('ё','е').replace('–','-').replace('—','-')
    s=re.sub(r'[^а-яa-z0-9]+',' ',s).strip()
    s=re.sub(r'\s+',' ',s)
    if s in SPECIAL:return SPECIAL[s]
    s=re.sub(r'^республика\s+','',s)
    if s in SPECIAL: return SPECIAL[s]
    s=re.sub(r'\s+(область|республика|край)$','',s)
    return SPECIAL.get(s,s)

def read_csv(p):
    errors=[]
    for enc in ('utf-8-sig','utf-8','cp1251'):
        for sep in (';',',','\t'):
            try:
                df=pd.read_csv(p,encoding=enc,sep=sep,dtype=str,low_memory=False,on_bad_lines='warn')
                if len(df.columns)>=2:
                    df.columns=[str(c).strip().lstrip('\ufeff') for c in df.columns]
                    return df
            except Exception as e:errors.append(str(e)[:60])
    raise ValueError(f'Cannot parse CSV {p}: {errors[:2]}')

def guess_column(df,kind):
    colnames=list(df.columns); normc={c:re.sub('[^a-zа-я0-9]+','',c.lower().replace('ё','е')) for c in colnames}
    variants={
        'region':['regionname','territoryname','subjectname','territory','region','subject','регион','названиерегиона','наименованиерегиона','территория','наименованиетерритории','субъектрф','наименованиеобъекта','geo','география'],
        'year':['year','год','period','период','obs_year','periodyear'],
        'code':['indicatorcode','indicatorid','кодпоказателя','кодиндикатора','code','indicator','idindicator','показателькод','indicator_code'],
        'value':['value','значение','indicatorvalue','obsvalue','valuefact','val','data','показательзначение'],
    }
    for label in variants[kind]:
        for c in colnames:
            if normc[c]==label:return c
    for label in variants[kind]:
        for c in colnames:
            if label in normc[c]:return c
    if kind=='region':
        for c in colnames:
            vals=df[c].dropna().astype(str)
            if len(vals) and vals.str.contains('область|край|республик|округ|москва|санкт',case=False,regex=True).sum()>min(5,len(vals)*.1):return c
    return None

def select_indicator(df,code,p):
    year=guess_column(df,'year')
    codecol=guess_column(df,'code')
    out=df.copy()
    if codecol is not None:
        selected=(out[codecol].astype(str).str.strip().str.replace('.0','',regex=False)==code)
        if selected.any():out=out[selected].copy()
        elif code not in p.name: return None
    elif code not in p.name and not any(code in str(c) for c in out.columns):
        return None
    if year:
        out=out[out[year].astype(str).str.contains(r'(?<!\d)2021(?!\d)',regex=True,na=False)].copy()
    if out.empty:return None
    reg=guess_column(out,'region')
    if not reg:
        return None
    val=guess_column(out,'value')
    wide=[c for c in out.columns if '2021' in str(c)]
    codewide=[c for c in out.columns if code in str(c)]
    if (year is None) and wide:val=wide[0]
    if val is None and codewide:val=codewide[0]
    if val is None:
        possible=[c for c in out.columns if c not in [year,reg,codecol] and 
                  pd.to_numeric(out[c].astype(str).str.replace(',','.'),errors='coerce').notna().sum()>10]
        if len(possible)==1:val=possible[0]
    if val is None:return None
    out=out[[reg,val]].rename(columns={reg:'region',val:'value'})
    out['value']=pd.to_numeric(out['value'].astype(str).str.replace(',','.').str.replace(' ','').str.replace('\xa0',''),errors='coerce')
    out=out[~out['region'].astype(str).str.contains('Федеральный округ|Российская Федерация|^Россия$|Central Federal District',case=False,regex=True)]
    out['key']=out['region'].map(norm)
    out=out[(out['key']!='') & out['value'].notna()].copy()
    # Source may have duplicate names from aggregate lines. Preserve diagnostics rather than average silently.
    conflicts=out.groupby('key').value.nunique()
    if (conflicts>1).any():
        raise ValueError(f'Ambiguous multiple values in {p.name} for {list(conflicts[conflicts>1].index)}')
    out=out.drop_duplicates('key')
    if len(out)<40:return None
    logging.info('%s: %s regions from %s',code,len(out),p.name)
    return out

def load_source_stats():
    files=list((ROOT/'data'/'raw').rglob('*.csv'))
    if not files:raise FileNotFoundError('Missing population CSV files in data/raw. Run download_sources.py (7-Zip required for .rar).')
    datafiles=[]
    for p in files:
        try: datafiles.append((p,read_csv(p)))
        except Exception as e: logging.warning('Skip CSV %s: %s',p.name,e)
    values=[]
    for nm,(code,desc) in FEATURES.items():
        candidates=[]
        for p,df in datafiles:
            hit=select_indicator(df,code,p)
            if hit is not None: candidates.append((len(hit),p,hit))
        if not candidates:
            raise ValueError(f'Indicator {code} missing from parsed 2021 CSV data. Inspect schema and data/raw. Columns: '+str([(p.name,list(df.columns)[:8]) for p,df in datafiles][:8]))
        _,src,tbl=max(candidates,key=lambda t:t[0])
        logging.info('Using source %s for %s',src.name,code)
        tbl=tbl.rename(columns={'value':nm,'region':f'source_name_{nm}'})
        values.append(tbl)
    stats=values[0]
    for t in values[1:]:stats=stats.merge(t,on='key',how='outer',validate='one_to_one')
    return stats

def load_geo():
    file=ROOT/'data'/'raw'/'regions_2021.geojson'
    if not file.exists():raise FileNotFoundError('Missing data/raw/regions_2021.geojson. Run download_sources.py')
    g=gpd.read_file(file)
    if g.crs is None:
        # Explicit source is geographic GeoJSON WGS84; confirm plausible extent.
        bb=g.total_bounds
        if not(-180<=bb[0]<=180 and -90<=bb[1]<=90 and -180<=bb[2]<=180 and -90<=bb[3]<=90):
            raise ValueError('Missing CRS and coordinates outside WGS84 range')
        g=g.set_crs('EPSG:4326')
    g=g.to_crs(4326)
    candidates=[c for c in g.columns if str(c).lower() in ('name','name_ru','region','region_name','name_rus','subject','title','regionname')]
    if not candidates:
        raise ValueError('Unknown GeoJSON name fields: '+str(list(g.columns)))
    col=candidates[0]
    g['geo_name']=g[col].astype(str)
    g['key']=g['geo_name'].map(norm)
    g=g[['key','geo_name','geometry']].copy()
    invalid=(~g.is_valid)&g.geometry.notna()
    if invalid.any():
        logging.warning('Repair %s invalid geometries via buffer(0)',int(invalid.sum()))
        g.loc[invalid,'geometry']=g.loc[invalid,'geometry'].buffer(0)
    g=g[~g.geometry.is_empty & g.geometry.notna()].copy()
    if g.key.duplicated().any():
        # Only dissolve features with identical normalized keys, not unrelated regions.
        g=g.dissolve(by='key',aggfunc='first').reset_index()
    return g

def fake_fixture():
    """Fictional data only; labels and output dirs reveal demo status."""
    rng=np.random.default_rng(2026)
    rows=[]
    for i in range(8):
        for j in range(6):
            idx=6*i+j+1; latent=(i>=4)+(j>=3); jitter=rng.normal(0,.75)
            rows.append({'key':f'тестовый район {idx:02d}','geo_name':f'ТЕСТ {idx:02d}',
                'urban_share':np.clip(50+12*latent+4*jitter+rng.normal(0,6),0,100),
                'natural_change':-9+4*latent-1.2*j+rng.normal(0,1.5),
                'migration_change':-3+3*i-2*j+rng.normal(0,4),
                'fertility':1.2+.17*latent+rng.normal(0,.15),
                'geometry':box(i,j,i+.94,j+.94)})
    g=gpd.GeoDataFrame(rows,geometry='geometry',crs=4326)
    return g

def load_real():
    stats=load_source_stats(); geo=load_geo()
    stats_keys=set(stats.key); geo_keys=set(geo.key)
    audit={'source_regions':len(stats),'geometry_regions':len(geo),
           'stats_missing_geography':sorted(stats_keys-geo_keys),
           'geography_missing_stats':sorted(geo_keys-stats_keys)}
    (ROOT/'results'/'join_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    if len(stats_keys&geo_keys)<55:
        raise ValueError('Too few matching regions; inspect results/join_audit.json. No fuzzy joins are made automatically.')
    g=geo.merge(stats,on='key',how='inner',validate='one_to_one')
    for c in FN:g[c]=pd.to_numeric(g[c],errors='coerce')
    counts=g[FN].isna().sum()
    logging.info('Joined %s regions; missing by variable = %s',len(g),counts.to_dict())
    return g,audit

def spatial_neighbors(g,k=4):
    pts=g.geometry.representative_point()
    xy=np.column_stack([pts.y.to_numpy(),pts.x.to_numpy()])
    d=haversine_distances(np.radians(xy))*6371.0088
    np.fill_diagonal(d,np.inf)
    A=np.zeros((len(g),len(g)),int)
    for i in range(len(g)):
        A[i,np.argsort(d[i])[:k]]=1
    A=np.maximum(A,A.T)
    G=nx.from_numpy_array(A)
    # kNN can form disconnected components on remote islands: bridge minimum centroid distances.
    bridge_edges=[]
    while not nx.is_connected(G):
        components=[sorted(c) for c in nx.connected_components(G)]
        choices=[(d[i,j],i,j) for ii,a in enumerate(components) for b in components[ii+1:] for i in a for j in b]
        dist,i,j=min(choices)
        A[i,j]=A[j,i]=1; G.add_edge(i,j)
        bridge_edges.append({'i':int(i),'j':int(j),'kilometres':float(dist)})
    np.fill_diagonal(A,0)
    return A,d,bridge_edges

def moran(z,A,nperm=399,seed=42):
    rng=np.random.default_rng(seed); z=np.asarray(z,float);z=z-z.mean()
    W=A.astype(float); W/=W.sum(axis=1,keepdims=True)
    denom=float((z*z).sum());m2=denom/len(z)
    glob=float(len(z)/W.sum()*((W@z)*z).sum()/denom)
    sims=[]
    local=z*(W@z)/m2
    local_sims=[]
    for _ in range(nperm):
        zz=rng.permutation(z)
        sims.append(float(len(z)/W.sum()*(zz@(W@zz))/denom))
        local_sims.append(zz*(W@zz)/m2)
    sims=np.array(sims);ls=np.asarray(local_sims)
    gp=(np.count_nonzero(abs(sims-sims.mean())>=abs(glob-sims.mean()))+1)/(nperm+1)
    # Permutation p-values are *unconditional* exploratory local Moran, not formal conditional LISA.
    lp=(np.count_nonzero(abs(ls)>=abs(local)[None,:],axis=0)+1)/(nperm+1)
    q=bh(lp)
    lag=W@z
    typ=np.where((z>=0)&(lag>=0),'HH',np.where((z<0)&(lag<0),'LL',np.where(z>=0,'HL','LH')))
    return glob,gp,local,lp,q,typ

def bh(p):
    p=np.asarray(p,float);n=len(p);ids=np.argsort(p)
    ranked=np.minimum.accumulate((p[ids]*n/np.arange(1,n+1))[::-1])[::-1]
    q=np.zeros(n);q[ids]=np.clip(ranked,0,1)
    return q

def labels_mst(X,A,k):
    graph=nx.Graph()
    graph.add_nodes_from(range(len(X)))
    for i,j in zip(*np.where(np.triu(A,1)>0)):
        w=float(np.linalg.norm(X[i]-X[j]))
        graph.add_edge(int(i),int(j),weight=w)
    tree=nx.minimum_spanning_tree(graph,weight='weight')
    cuts=sorted(tree.edges(data='weight'),key=lambda e:e[2],reverse=True)[:k-1]
    for i,j,_ in cuts:tree.remove_edge(i,j)
    labels=np.zeros(len(X),dtype=int)
    for c,nodes in enumerate(nx.connected_components(tree)):
        for i in nodes:labels[i]=c
    return labels

def cluster_method(method,X,A,k,seed=42):
    if method=='KMeans':return KMeans(n_clusters=k,n_init=20,random_state=seed).fit_predict(X)
    if method=='Spatial Ward':return AgglomerativeClustering(n_clusters=k,linkage='ward',connectivity=csr_matrix(A)).fit_predict(X)
    if method=='MST spatial':return labels_mst(X,A,k)
    raise ValueError(method)

def fragmentation(labels,A):
    return sum(nx.number_connected_components(nx.from_numpy_array(A[np.ix_(labels==c,labels==c)])) for c in np.unique(labels))

def stability(method,X,A,k):
    rng=np.random.default_rng(1984)
    lbl0=cluster_method(method,X,A,k,42)
    return float(np.mean([adjusted_rand_score(lbl0,cluster_method(method,X+rng.normal(0,.07,X.shape),A,k,42+i)) for i in range(10)]))

def draw_map(g, column, out, title, categorical=False, missing_geo=None):
    """A slide-ready map with a descriptive title, legend, units, and visible data status."""
    from matplotlib.colors import Normalize
    from matplotlib import cm
    from matplotlib.patches import Patch
    # Russia spans the 180th meridian: negative longitudes in Chukotka must
    # appear to the RIGHT of the Far East, not on the far left of the map.
    # Shift only drawing geometries; original WGS84 geometries remain unchanged
    # for neighbors, distances and exported spatial data.
    from shapely.ops import transform as shapely_transform
    def _wrapped_for_russia(frame):
        if frame is None or frame.empty:
            return frame
        frame = frame.copy()
        def _wrap(x, y, z=None):
            xx = np.asarray(x, dtype=float)
            xx = np.where(xx < 0, xx + 360.0, xx)
            if z is None:
                return (xx, y)
            return (xx, y, z)
        frame['geometry'] = frame.geometry.map(lambda geom: shapely_transform(_wrap, geom))
        return frame
    g = _wrapped_for_russia(g)
    missing_geo = _wrapped_for_russia(missing_geo)
    fig, ax = plt.subplots(figsize=(15.5, 6.5), dpi=165)
    fig.patch.set_facecolor('#FFFFFF')
    ax.set_facecolor('#FFFFFF')
    # Regions without matching 2021 statistics must remain visible on maps,
    # but MUST NOT be assigned a fictional cluster or indicator value.
    has_missing = missing_geo is not None and not missing_geo.empty
    if has_missing:
        missing_geo.plot(ax=ax, facecolor='#DEE2E8', edgecolor='#8795A6',
                         linewidth=.7, hatch='///', zorder=1)
    if categorical:
        cats = sorted(g[column].dropna().unique())
        entries = []
        for cat in cats:
            color = COLORS[int(cat) % len(COLORS)]
            part = g[g[column] == cat]
            part.plot(ax=ax, color=color, edgecolor='#667282', linewidth=.36)
            entries.append(Patch(color=color, label=f'Группа {int(cat)+1}  ·  {len(part)} террит.'))
        if has_missing:
            entries.append(Patch(facecolor='#DEE2E8', edgecolor='#8795A6',
                                 hatch='///',label=f'Нет данных  ·  {len(missing_geo)} террит.'))
        ax.legend(handles=entries, title='Цвет обозначает группу', title_fontsize=13,
                  loc='lower left', frameon=True, facecolor='white', edgecolor='#CFD8E3',fontsize=12)
        note = 'Регионы одного цвета имеют сходные характеристики. Цвет не означает «лучше» или «хуже».'
    else:
        cmap='viridis'
        values=g[column].astype(float)
        minv,maxv=float(values.min()),float(values.max())
        if minv==maxv:maxv=minv+1
        normcolor=Normalize(vmin=minv,vmax=maxv)
        g.plot(column=column, ax=ax, cmap=cmap, edgecolor='#D3DCE4', linewidth=.3,
               legend=False, missing_kwds={'color':'#D6D6D6'})
        unit = {'urban_share':'% населения', 'natural_change':'на 1000 человек (‰)',
                'migration_change':'на 1000 человек (‰)', 'fertility':'детей на женщину'}.get(column,'значение')
        sm=cm.ScalarMappable(norm=normcolor,cmap=cmap)
        sm.set_array([])
        bar=fig.colorbar(sm,ax=ax,shrink=.65, fraction=.025, pad=.03)
        bar.ax.tick_params(labelsize=11)
        bar.set_label(unit,fontsize=12)
        note = f'Шкала viridis: фиолетовый — ниже, жёлтый — выше. Минимум {minv:.2f}; максимум {float(values.max()):.2f}.'
        if has_missing:
            from matplotlib.patches import Patch
            ax.legend(handles=[Patch(facecolor='#DEE2E8', edgecolor='#8795A6',
                                    hatch='///',label=f'Серый со штриховкой: нет данных ({len(missing_geo)})')],
                      loc='lower left',fontsize=11,frameon=True,facecolor='white')
    if has_missing:
        note = 'Серый со штриховкой — нет полного набора данных за 2021 год. ' + (
            'Цветные регионы объединены по демографическому сходству.' if categorical
            else f'Цветная шкала: минимум {minv:.2f}, максимум {float(values.max()):.2f}.')
    ax.set_title(title, fontsize=19, fontweight='bold', loc='left', pad=11)
    # Fit the whole Russian territory, including Chukotka, into the image area.
    all_bounds = np.array([g.total_bounds] + ([missing_geo.total_bounds] if has_missing else []))
    xmin,ymin = np.min(all_bounds[:, :2],axis=0)
    xmax,ymax = np.max(all_bounds[:, 2:],axis=0)
    padx=max((xmax-xmin)*.04,.1); pady=max((ymax-ymin)*.08,.1)
    ax.set_xlim(xmin-padx,xmax+padx)
    ax.set_ylim(ymin-pady,ymax+pady)
    ax.set_aspect('auto')  # full width, larger regions; longitude remains unwrapped
    ax.axis('off')
    fig.text(.05,.042,note,fontsize=11,color='#34465B')
    fig.text(.05,.014,('ТЕСТ: ВЫМЫШЛЕННЫЕ ПОЛИГОНЫ И ПОКАЗАТЕЛИ — НЕ СТАТИСТИКА РОССИИ' if 'demo' in str(out).lower() else 'Субъекты РФ • 2021 год • источники: Росстат / Если быть точным и GeoJSON'),fontsize=9,color='#657488')
    fig.subplots_adjust(left=.025,right=.95,top=.90,bottom=.105)
    fig.savefig(out, bbox_inches='tight', facecolor='white')
    plt.close(fig)

def main(demo=False):
    out=ROOT/('results_demo' if demo else 'results')
    mapdir=ROOT/('maps_demo' if demo else 'maps')
    out.mkdir(exist_ok=True);mapdir.mkdir(exist_ok=True)
    t0=time.time()
    try:
        if demo:g=fake_fixture();audit={'demo_data':True,'n':len(g)}
        else:g,audit=load_real()
        g=g.reset_index(drop=True)
        valid=g[FN].notna().all(axis=1)
        excluded=g.loc[~valid,['key']].copy()
        excluded.to_csv(out/'excluded_missing.csv',index=False,encoding='utf-8-sig')
        unfiltered=g.copy()
        g=g.loc[valid].reset_index(drop=True)
        missing_geo=None
        missing_details=[]
        if not demo:
            # The source polygons are independent of the statistics. Preserve them.
            all_geography=load_geo()
            used_keys=set(g.key)
            matching_keys=set(unfiltered.key)
            missing_geo=all_geography[~all_geography.key.isin(used_keys)].copy()
            for rec in missing_geo[['geo_name','key']].to_dict('records'):
                reason=('no_matching_statistics_or_name_mismatch'
                        if rec['key'] not in matching_keys else 'incomplete_2021_indicators')
                missing_details.append({'region':rec['geo_name'],'key':rec['key'],'reason':reason})
            pd.DataFrame(missing_details,columns=['region','key','reason']).to_csv(
                out/'excluded_regions_map.csv',index=False,encoding='utf-8-sig')
            if len(missing_geo):
                logging.warning('%s regions have no complete matched 2021 data and are drawn GRAY, not omitted: %s',
                                len(missing_geo), ', '.join(missing_geo.geo_name.tolist()))
        if len(g)<25:raise ValueError('Fewer than 25 complete regions after exclusions; investigate.')
        if (g.urban_share.lt(0)|g.urban_share.gt(100)|g.fertility.lt(0)).any():raise ValueError('Impossible urban_share or fertility; check source parsing')
        X=StandardScaler().fit_transform(g[FN])
        A,d,bridges=spatial_neighbors(g,4)
        np.savetxt(out/'neighbors_matrix.csv',A,fmt='%d',delimiter=',')
        pd.DataFrame({'region':g.geo_name,'key':g.key}).to_csv(out/'region_keys.csv',index=False,encoding='utf-8-sig')
        descriptive=g[FN].agg(['count','mean','std','median','min','max']).T
        descriptive['skew']=g[FN].apply(lambda s:skew(s, bias=False))
        descriptive.to_csv(out/'descriptive.csv',encoding='utf-8-sig')
        morans=[]; localdata=g[['key','geo_name']].copy()
        for i,(nm,(code,desc)) in enumerate(FEATURES.items()):
            I,p,li,lp,q,typ=moran(g[nm],A,399,seed=42+i)
            morans.append({'variable':nm,'indicator_code':code,'Moran_I':I,'permutation_p':p,
                           'local_FDR05_n':int((q<.05).sum())})
            localdata[f'{nm}_local_I']=li
            localdata[f'{nm}_q']=q
            localdata[f'{nm}_type']=typ
            draw_map(g,nm,mapdir/f'{nm}.png',desc,missing_geo=missing_geo)
        localdata.to_csv(out/'local_moran.csv',index=False,encoding='utf-8-sig')
        pd.DataFrame(morans).to_csv(out/'global_moran.csv',index=False,encoding='utf-8-sig')
        results=[]; stored={}
        for method in ('KMeans','Spatial Ward','MST spatial'):
            for k in (3,4,5,6):
                y=cluster_method(method,X,A,k)
                counts=np.bincount(y)
                metrics={'method':method,'k':k,'silhouette':float(silhouette_score(X,y)),
                         'davies_bouldin':float(davies_bouldin_score(X,y)),
                         'stability_ARI':stability(method,X,A,k),
                         'connected_components':fragmentation(y,A),'min_cluster_size':int(counts.min()),
                         'max_cluster_size':int(counts.max())}
                results.append(metrics);stored[(method,k)]=y
        r=pd.DataFrame(results)
        # Penalize extremely small clusters; explicit interpretable composite, not a universal theorem.
        r['fragment_score']=r.k/r.connected_components
        r['silhouette_score']=(r.silhouette+1)/2
        r['balanced_score']=.55*r.silhouette_score+.25*r.stability_ARI+.20*r.fragment_score
        r.loc[r.min_cluster_size<3,'balanced_score']-=.15
        r.sort_values('balanced_score',ascending=False).to_csv(out/'method_comparison.csv',index=False,encoding='utf-8-sig')
        best=r.sort_values('balanced_score',ascending=False).iloc[0]
        method,k=str(best.method),int(best.k)
        g['cluster']=stored[(method,k)]
        labels= g[['geo_name','key','cluster']+FN].sort_values('cluster')
        labels.to_csv(out/'regional_clusters.csv',index=False,encoding='utf-8-sig')
        g.to_file(out/'regions_clusters.geojson',driver='GeoJSON')
        means=g.groupby('cluster')[FN].agg(['count','mean'])
        means.to_csv(out/'cluster_profiles.csv',encoding='utf-8-sig')
        draw_map(g,'cluster',mapdir/'clusters_final.png',f'Кластеры: {method}, k={k}',categorical=True,missing_geo=missing_geo)
        for m in ('KMeans','Spatial Ward','MST spatial'):
            ky=int(r[r.method==m].sort_values('balanced_score',ascending=False).iloc[0].k)
            g[f'cluster_{m.replace(" ","_")}']=stored[(m,ky)]
            draw_map(g,f'cluster_{m.replace(" ","_")}',mapdir/f'cluster_{m.replace(" ","_")}.png',f'{m}, k={ky}',categorical=True,missing_geo=missing_geo)
        prof=g.groupby('cluster')[FN].mean()
        profz=(prof-g[FN].mean())/g[FN].std(ddof=0)
        # Heatmap of standardized effects. Explanatory units and direction for audience.
        fig,ax=plt.subplots(figsize=(11.5,5.55),dpi=170)
        im=ax.imshow(profz.to_numpy(),cmap='RdBu_r',vmin=-2,vmax=2,aspect='auto')
        ax.set_xticks(range(4),['Городское\nнаселение','Естественный\nприрост',
                                    'Миграционный\nприрост','Рождаемость'])
        ax.set_yticks(range(k),[f'Группа {i+1}  ({int((g.cluster==i).sum())} регионов)' for i in prof.index])
        ax.set_title('Чем группы отличаются от среднего?',fontsize=18,loc='left',fontweight='bold',pad=15)
        for ii in range(k):
            for jj in range(4):
                xval=profz.iloc[ii,jj]
                ax.text(jj,ii,f'{xval:+.2f}',ha='center',va='center',fontsize=11,
                        color='white' if abs(xval)>1.1 else '#12243A',weight='bold')
        cbar=fig.colorbar(im,ax=ax,shrink=.88,pad=.03)
        cbar.set_label('Отклонение в стандартных единицах',fontsize=11)
        ax.tick_params(length=0,labelsize=11)
        fig.text(.19,.01,'Синий — ниже среднего по всем территориям; красный — выше. Числа внутри клеток показывают величину отличия.',
                 fontsize=10,color='#33475B')
        fig.subplots_adjust(left=.20,right=.93,bottom=.18,top=.85)
        fig.savefig(mapdir/'cluster_profiles.png',bbox_inches='tight',facecolor='white');plt.close(fig)

        # Comparison graph with labeled metric, direction, legend, and the best point.
        fig,ax=plt.subplots(figsize=(11.5,6),dpi=165)
        names={'KMeans':'K-Means · без географии','Spatial Ward':'Spatial Ward · по соседству',
               'MST spatial':'MST · по графу соседства'}
        mark={'KMeans':'o','Spatial Ward':'s','MST spatial':'D'}
        col={'KMeans':'#2077AC','Spatial Ward':'#D8871E','MST spatial':'#8962B6'}
        for m,grp in r.groupby('method'):
            grp=grp.sort_values('k')
            ax.plot(grp.k,grp.silhouette,marker=mark[m],label=names[m],linewidth=2.7,
                    markersize=8,color=col[m])
            for _,rw in grp.iterrows():
                ax.annotate(f'{rw.silhouette:.2f}',(rw.k,rw.silhouette),xytext=(0,10),
                            textcoords='offset points',ha='center',fontsize=10,color=col[m])
        ax.set_title('Какие алгоритмы разделяют регионы лучше?',fontsize=18,fontweight='bold',loc='left',pad=20)
        ax.set_xlabel('Количество групп (k)',fontsize=13)
        ax.set_ylabel('Silhouette — выше означает лучшее разделение',fontsize=12)
        ax.set_xticks([3,4,5,6]);ax.grid(alpha=.2,axis='y')
        ymin,ymax=float(r.silhouette.min()),float(r.silhouette.max())
        ax.set_ylim(min(-.05,ymin-.07),min(1,ymax+.10))
        ax.legend(loc='lower left',fontsize=10,frameon=True,ncol=1)
        fig.text(.1,.012,'Важно: силуэт не учитывает географическую связность и устойчивость; итоговый выбор использует несколько критериев.',
                 fontsize=10,color='#33475B')
        fig.subplots_adjust(left=.12,right=.96,bottom=.18,top=.85)
        fig.savefig(mapdir/'method_silhouette.png',bbox_inches='tight',facecolor='white');plt.close(fig)

        # Global spatial autocorrelation chart for a slide-ready explanation.
        mdf=pd.DataFrame(morans)
        fig,ax=plt.subplots(figsize=(11.5,5.5),dpi=165)
        descriptions=['Городское население','Естественный прирост','Миграционный прирост','Рождаемость']
        colors=['#1D79B2' if x>=0 else '#D77A25' for x in mdf.Moran_I]
        bars=ax.barh(descriptions,mdf.Moran_I.to_numpy(),height=.59,color=colors)
        ax.invert_yaxis()
        ax.axvline(0,color='#6A7582',linewidth=1.2)
        for bar,(_,row) in zip(bars,mdf.iterrows()):
            val=float(row.Moran_I)
            ax.text(val+(.01 if val>=0 else -.01),bar.get_y()+bar.get_height()/2,
                    f'I={val:+.2f}  ·  p={float(row.permutation_p):.3f}',
                    va='center',ha='left' if val>=0 else 'right',fontsize=11,fontweight='bold')
        ax.set_xlim(min(-.3,float(mdf.Moran_I.min())-.18),max(.95,float(mdf.Moran_I.max())+.30))
        ax.set_xlabel('Индекс Морана I (положительный — у соседей похожие значения)',fontsize=12)
        ax.tick_params(axis='y',labelsize=12)
        ax.grid(axis='x',alpha=.18)
        ax.set_title('Есть ли пространственное сходство между соседями?',fontsize=18,fontweight='bold',loc='left',pad=15)
        fig.text(.16,.015,'p рассчитано по 399 случайным перестановкам. Низкое p — аргумент против случайного расположения показателя.',
                 fontsize=10,color='#33475B')
        fig.subplots_adjust(left=.24,right=.93,bottom=.20,top=.86)
        fig.savefig(mapdir/'moran_global.png',bbox_inches='tight',facecolor='white');plt.close(fig)
        # Scaling-sensitivity test: refit three method choices with RobustScaler, measure ARI.
        Xr=RobustScaler().fit_transform(g[FN]); sensitivity=[]
        for m in ('KMeans','Spatial Ward','MST spatial'):
            ky=int(r[r.method==m].sort_values('balanced_score',ascending=False).iloc[0].k)
            sensitivity.append({'method':m,'k':ky,'standard_vs_robust_ARI':adjusted_rand_score(stored[(m,ky)],cluster_method(m,Xr,A,ky))})
        pd.DataFrame(sensitivity).to_csv(out/'sensitivity_scaler.csv',index=False,encoding='utf-8-sig')
        summary={'status':'synthetic_demo_not_real_data' if demo else 'completed_2021_data',
                 'n_regions':len(g),'n_raw_geographies':int(audit.get('geometry_regions',len(g))),
                 'excluded_missing':int(len(excluded)),'excluded_unmapped_or_unmatched':len(missing_details),
                 'excluded_region_names':[row['region'] for row in missing_details],
                 'bridge_edges':bridges,
                 'best_method':method,'best_k':k,'best_silhouette':float(best.silhouette),
                 'best_stability_ARI':float(best.stability_ARI),
                 'selected_cluster_counts':g.cluster.value_counts().sort_index().to_dict(),
                 'moran':morans,'features':{v[0]:v[1] for v in FEATURES.values()},
                 'geometry_source':'https://github.com/imsha/russia_geojson_regions_2021',
                 'statistics_source':'https://github.com/tochno-st/regions_collection',
                 'processing_s':round(time.time()-t0,1)}
        (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(summary,ensure_ascii=False,indent=2))
        print('DONE; output dir:',out)
        return 0
    except Exception as e:
        logging.exception('Analysis failed; real-data results were NOT fabricated')
        (out/'run_log.txt').write_text(f'ERROR: {type(e).__name__}: {e}\n',encoding='utf-8')
        return 1
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--demo',action='store_true',help='FICTIONAL synthetic smoke test, not coursework results')
    sys.exit(main(p.parse_args().demo))
