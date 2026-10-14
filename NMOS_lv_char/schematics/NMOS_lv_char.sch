v {xschem version=3.4.8RC file_version=1.3}
G {}
K {}
V {}
S {}
F {}
E {}
N -150 -30 -150 20 {lab=VG}
N -150 -30 -90 -30 {lab=VG
}
N -150 80 -150 100 {lab=0}
N -50 -80 -50 -60 {lab=VD}
N -50 -80 150 -80 {lab=VD}
N 150 -80 150 20 {lab=VD}
N 150 80 150 100 {lab=0}
N -50 80 -50 100 {lab=0}
N 50 80 50 100 {lab=0}
N -50 0 -50 20 {lab=VS}
N -50 -30 50 -30 {lab=VB}
N 50 -30 50 20 {lab=VB}
C {sg13g2_pr/sg13_lv_nmos.sym} -70 -30 0 0 {name=M1
l=\{L_n\}
w=\{W_n\}
ng=\{NG_n\}
m=\{M_n\}
mm_ok=1
model=sg13_lv_nmos
spiceprefix=X
}
C {vsource.sym} -150 50 0 0 {name=V1 value=\{Vg\} savecurrent=false}
C {vsource.sym} 150 50 0 0 {name=V2 value=\{Vd\} savecurrent=false}
C {gnd.sym} -150 100 0 0 {name=l1 lab=0}
C {gnd.sym} 150 100 0 0 {name=l3 lab=0}
C {lab_wire.sym} -120 -30 0 0 {name=p1 sig_type=std_logic lab=VG

}
C {lab_wire.sym} 20 -80 0 0 {name=p2 sig_type=std_logic lab=VD}
C {simulator_commands_shown.sym} 230 -20 0 0 {
        name=Libs_Ngspice
        simulator=ngspice
        only_toplevel=false
        value="
.lib cornerMOSlv.lib \{CORNER_MOS_lv\}
*.lib cornerMOShv.lib \{CORNER_MOS_hv\}
*.lib cornerHBT.lib \{CORNER_HBT\}
*.lib cornerRES.lib \{CORNER_RES\}
*.lib cornerCAP.lib \{CORNER_CAP\}
"
      }
C {vsource.sym} -50 50 0 0 {name=V3 value=\{Vs\} savecurrent=false}
C {gnd.sym} -50 100 0 0 {name=l2 lab=0}
C {vsource.sym} 50 50 0 0 {name=V4 value=\{Vb\} savecurrent=false}
C {gnd.sym} 50 100 0 0 {name=l4 lab=0}
C {lab_wire.sym} 50 -30 0 0 {name=p3 sig_type=std_logic lab=VB}
C {lab_wire.sym} -50 20 0 0 {name=p4 sig_type=std_logic lab=VS}
C {code_shown.sym} -390 -90 0 0 {name=parametry
value="
.param Vg=0.6
.param Vd=1.2
.param Vs=0
.param Vb=0
.param W_n=0.15u
.param L_n=0.13u
.param M_n=1
.param NG_n=1
.param TEMP=25
.temp \{TEMP\}
"}
