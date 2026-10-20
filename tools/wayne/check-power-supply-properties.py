#!/usr/bin/env python3
"""Verify sysfs indexes match the public power supply property enum."""
from pathlib import Path
import re,subprocess,json
r=Path(__file__).resolve().parents[2]
h=(r/'include/linux/power_supply.h').read_text();c=(r/'drivers/power/supply/power_supply_sysfs.c').read_text()
enum=re.search(r'enum power_supply_property\s*\{(.*?)\n\};',h,re.S).group(1)
attrs=re.search(r'static struct device_attribute power_supply_attrs\[\]\s*=\s*\{(.*?)\n\};',c,re.S).group(1)
aliases={'bypass_vchg_loop_debouncer':'vchg_loop_dbc_bypass','temp_cool':'cool_temp','temp_warm':'warm_temp','temp_cold':'cold_temp','temp_hot':'hot_temp','safety_timer_enabled':'safety_timer_enable'}
res={}
for enabled in [False,True]:
 flags=['-DCONFIG_MACH_LONGCHEER=1']if enabled else []
 def cpp(t):return subprocess.check_output(['cpp','-P',*flags,'-'],input=t,text=True)
 es=re.findall(r'POWER_SUPPLY_PROP_([A-Z0-9_]+)',cpp(enum));ns=re.findall(r'POWER_SUPPLY_ATTR\(\s*([a-z0-9_]+)\s*\)',cpp(attrs));assert len(es)==len(ns),(len(es),len(ns))
 mismatches=[{'index':i,'sysfs_name':n,'actual_property':e.lower()}for i,(e,n)in enumerate(zip(es,ns))if e.lower()!=aliases.get(n,n)]
 res['longcheer_enabled'if enabled else'known_good_generic']={'count':len(es),'mismatches':mismatches}

for k,v in res.items():print(k,len(v['mismatches']),'mismatches',v['mismatches'][:5],v['mismatches'][-3:])

raise SystemExit(any(v["mismatches"] for v in res.values()))
