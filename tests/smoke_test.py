from pathlib import Path
import sys
p=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(p/'src'))
from analyze import fake_fixture, spatial_neighbors, cluster_method, fragmentation, moran, FN
from sklearn.preprocessing import StandardScaler
import numpy as np

g=fake_fixture()
assert len(g)==48
assert g.geometry.notna().all()
X=StandardScaler().fit_transform(g[FN]);assert np.isfinite(X).all()
A,dist,bridges=spatial_neighbors(g,4)
assert A.shape==(48,48) and np.all(A==A.T)
for method in ('KMeans','Spatial Ward','MST spatial'):
    labels=cluster_method(method,X,A,4)
    assert len(set(labels))==4
    if method!='KMeans':assert fragmentation(labels,A)==4
I,p,_,_,_,_=moran(g.urban_share,A,nperm=99)
assert np.isfinite(I) and 0 < p <= 1
print('PASS: 48 synthetic polygons; 3 algorithms; spatial adjacency; Moran.')
