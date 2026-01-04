//Parameters
int m = 300;
real L = 1;
real rho = 500.;
real mu = 0.1;

real uin = 1;
func fx = 0;
func fy = 0;
int[int] noslip = [1, 2, 4];
int[int] inflow = [3];

real dt = 0.1;
real T = 50;

real eps = 1e-3;

//Macros
macro div(u) (dx(u#x) + dy(u#y))//
macro grad(u) [dx(u), dy(u)]//
macro Grad(u) [grad(u#x), grad(u#y)]//

//Time
real cpu;
real tabcpu;

//mesh
border C1(t = 0, L){ x = t; y = 0; label = 1; }
border C2(t = 0, L){ x = L; y = t; label = 2; }
border C3(t = 0, L){ x = L-t; y = L; label = 3; }
border C4(t = 0, L){ x = 0; y = L-t; label = 4; }
mesh th = buildmesh( C1(m) + C2(m) + C3(m) + C4(m) );

fespace UPh(th, [P2,P2,P1]);
UPh [ux, uy, p];
UPh [uhx, uhy, ph];
UPh [upx, upy, pp];

//Solve
varf navierstokes([ux, uy, p], [uhx, uhy, ph])
  = int2d(th)(
      rho/dt* [ux, uy]'* [uhx, uhy]
    + mu* (Grad(u):Grad(uh))
    - p* div(uh)
    - ph* div(u)
    - 1e-10 *p*ph
    )

  + int2d(th) (
      [fx, fy]' * [uhx, uhy]
    + rho/dt* [convect([upx, upy], -dt, upx), convect([upx, upy], -dt, upy)]'* [uhx, uhy]
    )

  + on(noslip, ux=0, uy=0)
  + on(inflow, ux=uin, uy=0)
  ;

//Initialization
[ux, uy, p]=[0, 0, 0];

matrix<real> NS = navierstokes(UPh, UPh, solver=sparsesolver);
real[int] NSrhs = navierstokes(0, UPh);

//Time loop
for(int j = 0; j < T/dt; j++){
  [upx, upy, pp]=[ux, uy, p];

  NSrhs = navierstokes(0, UPh);
  ux[] = NS^-1 * NSrhs;

  plot( [ux,uy], p, wait=0, cmm=j);
}

//CPU
cout << " CPU = " << clock()-cpu << endl ;
tabcpu = clock()-cpu;
