from string import Template
from math import sin,cos,radians,pi,sqrt

def create_dict(*args):
  return dict({i:eval(i) for i in args})


# ---- Input parameters ----
# Geometry
Rin = 0.0015          # Radius at Inlet 
b = 0.001             # Gap Height
Rout = 0.095          # Radius at Outlet

# Mesh size
NPA = 60         # X     
NPZ = 60         # Y
NPB = 1          # Height   (here: 2D-Case) 
             

b2 = b/2 
r2i = Rin/sqrt(2) 
r2o = Rout/sqrt(2)

d = create_dict('Rin','Rout','b','b2','NPA','NPZ','NPB','r2i','r2o')

t = Template("""FoamFile
{
    version     8;
    format      ascii;
    class       dictionary;
    object      blockMeshDict;
}

convertToMeters 1.0;

vertices 
(
 // --- bottom (z = -b/2) 
    ( $Rin 0 -$b2 ) // 0 
    ( 0 $Rin -$b2 ) // 1 
    ( -$Rin 0 -$b2 ) // 2
    ( 0 -$Rin -$b2 ) // 3 
    ( $Rout 0 -$b2 ) // 4 
    ( 0 $Rout -$b2 ) // 5 
    ( -$Rout 0 -$b2 ) // 6 
    ( 0 -$Rout -$b2 ) // 7 
             
 // --- top (z = +b/2) 
    ( $Rin 0 $b2 ) // 8 
    ( 0 $Rin $b2 ) // 9 
    ( -$Rin 0 $b2 ) // 10 
    ( 0 -$Rin $b2 ) // 11 
    ( $Rout 0 $b2 ) // 12 
    ( 0 $Rout $b2 ) // 13 
    ( -$Rout 0 $b2 ) // 14 
    ( 0 -$Rout $b2 ) // 15 
);		

blocks 
( 
    hex (0 4 5 1 8 12 13 9) ($NPA $NPZ $NPB) simpleGrading (1 1 1) 
    hex (1 5 6 2 9 13 14 10) ($NPA $NPZ $NPB) simpleGrading (1 1 1) 
    hex (2 6 7 3 10 14 15 11) ($NPA $NPZ $NPB) simpleGrading (1 1 1) 
    hex (3 7 4 0 11 15 12 8) ($NPA $NPZ $NPB) simpleGrading (1 1 1) 
);

edges
(
    // inner circle bottom
    arc 0 1 ( $r2i $r2i -$b2 )
    arc 1 2 ( -$r2i $r2i -$b2 )
    arc 2 3 ( -$r2i -$r2i -$b2 )
    arc 3 0 ( $r2i -$r2i -$b2 )
             
    // outer circle bottom
    arc 4 5 ( $r2o $r2o -$b2 ) 
    arc 5 6 ( -$r2o $r2o -$b2 )
    arc 6 7 ( -$r2o -$r2o -$b2 ) 
    arc 7 4 ( $r2o -$r2o -$b2 )
             
    // inner circle top
    arc 8 9 ( $r2i $r2i $b2 ) 
    arc 9 10 ( -$r2i $r2i $b2 ) 
    arc 10 11 ( -$r2i -$r2i $b2 ) 
    arc 11 8 ( $r2i -$r2i $b2 ) 
             
    // outer circle top 
    arc 12 13 ( $r2o $r2o $b2 ) 
    arc 13 14 ( -$r2o $r2o $b2 ) 
    arc 14 15 ( -$r2o -$r2o $b2 ) 
    arc 15 12 ( $r2o -$r2o $b2 ) 
);

patches
( 
    patch inlet
    ( 
        (0 1 9 8) 
        (1 2 10 9)
        (2 3 11 10) 
        (3 0 8 11) 
    ) 
             
    patch outlet 
    ( 
        (4 5 13 12) 
        (5 6 14 13) 
        (6 7 15 14) 
        (7 4 12 15) 
    ) 
             
    wall plates 
    ( 
        (0 4 5 1)
        (1 5 6 2)
        (2 6 7 3) 
        (3 7 4 0)
        (8 9 13 12)
        (9 10 14 13)
        (10 11 15 14)
        (11 8 12 15) 
    ) 
);

"""
)

print(t.substitute(d))
