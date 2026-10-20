#!/usr/bin/env python3
"""Host tests execute the driver's current selection and setter with I/O faults."""
from pathlib import Path
import subprocess
import tempfile
r = Path(__file__).resolve().parents[2]
s = (r / 'drivers/power/supply/qcom/smb1351-charger.c').read_text()
def function(name):
    start = s.index('static int ' + name + '(')
    brace = s.index('{', start)
    depth, end = 1, brace + 1
    while depth:
        depth += (s[end] == '{') - (s[end] == '}')
        end += 1
    return s[start:end]
header = r'''
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define max(a,b) ((a) > (b) ? (a) : (b))
#define USB2_MIN_CURRENT_MA 100
#define USB3_MIN_CURRENT_MA 150
#define USB3_MAX_CURRENT_MA 900
#define EINVAL 22
#define SMB1351_CHG_PRE_MIN_MA 100
#define SMB1351_CHG_FAST_MAX_MA 4500
#define MIN_FLOAT_MV 3500
#define MAX_FLOAT_MV 4508
static int usb_chg_current[] = {500,685,1000,1100,1200,1300,1500,1600,1700,1800,2000,2200,2500,3000};
enum power_supply_property {POWER_SUPPLY_PROP_CHARGING_ENABLED, POWER_SUPPLY_PROP_INPUT_SUSPEND, POWER_SUPPLY_PROP_CONSTANT_CHARGE_CURRENT_MAX, POWER_SUPPLY_PROP_CURRENT_MAX, POWER_SUPPLY_PROP_VOLTAGE_MAX};
union power_supply_propval {int intval;};
struct smb1351_charger {bool parallel_charger_suspended; int target_fastchg_current_max_ma,usb_psy_ma,vfloat_mv;};
struct power_supply {struct smb1351_charger *chip;};
static void *power_supply_get_drvdata(struct power_supply *p) {return p->chip;}
static int io_error, requested, calls;
#define USER 0
static int smb1351_usb_suspend(struct smb1351_charger *c,int reason,bool on) {return io_error;}
static int smb1351_parallel_set_chg_suspend(struct smb1351_charger *c,int on) {return io_error;}
static int smb1351_fastchg_current_set(struct smb1351_charger *c,int ma) {return io_error;}
static int smb1351_float_voltage_set(struct smb1351_charger *c,int mv) {return io_error;}
static int smb1351_set_usb_chg_current(struct smb1351_charger *c,int ma) {requested=ma;calls++;return io_error;}
'''
main = r'''
int main(void) {
 int supported[]={0,100,150,500,685,900,1000,1100,1200,1300,1500,1600,1700,1800,2000,2200,2500,3000};
 struct smb1351_charger c={0};struct power_supply p={&c}; union power_supply_propval v;
 for(int ua=0;ua<=5500000;ua+=137) {
  int want=0;for(int i=0;i<ARRAY_SIZE(supported);i++) if(supported[i]<=ua/1000)want=supported[i];
  v.intval=ua;assert(!smb1351_parallel_set_property(&p,POWER_SUPPLY_PROP_CURRENT_MAX,&v));
  assert(c.usb_psy_ma==want && requested==want && want*1000<=ua);
 }
 v.intval=0;assert(!smb1351_parallel_set_property(&p,POWER_SUPPLY_PROP_CURRENT_MAX,&v));assert(requested==0);
 c.usb_psy_ma=685;io_error=-5;v.intval=1200000;
 assert(smb1351_parallel_set_property(&p,POWER_SUPPLY_PROP_CURRENT_MAX,&v)==-5);assert(c.usb_psy_ma==685);
 int before=calls;v.intval=-1;assert(smb1351_parallel_set_property(&p,POWER_SUPPLY_PROP_CURRENT_MAX,&v)==-EINVAL);assert(calls==before);
 c.parallel_charger_suspended=true;v.intval=999999;
 assert(!smb1351_parallel_set_property(&p,POWER_SUPPLY_PROP_CURRENT_MAX,&v));assert(c.usb_psy_ma==900 && calls==before);
 c.target_fastchg_current_max_ma=1200;c.vfloat_mv=4400;
 v.intval=5100000;assert(smb1351_parallel_set_property(&p,POWER_SUPPLY_PROP_CONSTANT_CHARGE_CURRENT_MAX,&v)==-EINVAL);assert(c.target_fastchg_current_max_ma==1200);
 v.intval=0;assert(smb1351_parallel_set_property(&p,POWER_SUPPLY_PROP_VOLTAGE_MAX,&v)==-EINVAL);assert(c.vfloat_mv==4400);
 v.intval=1300000;assert(!smb1351_parallel_set_property(&p,POWER_SUPPLY_PROP_CONSTANT_CHARGE_CURRENT_MAX,&v));assert(c.target_fastchg_current_max_ma==1300);
 c.parallel_charger_suspended=false;io_error=-5;v.intval=1500000;
 assert(smb1351_parallel_set_property(&p,POWER_SUPPLY_PROP_CONSTANT_CHARGE_CURRENT_MAX,&v)==-5);assert(c.target_fastchg_current_max_ma==1300);
 v.intval=4300000;assert(smb1351_parallel_set_property(&p,POWER_SUPPLY_PROP_VOLTAGE_MAX,&v)==-5);assert(c.vfloat_mv==4400);
 return 0;
}
'''
with tempfile.TemporaryDirectory() as tmp:
    p = Path(tmp)
    (p/'test.c').write_text(header + function('smb1351_get_usb_current_limit') + '\n' + function('smb1351_parallel_set_property') + main)
    subprocess.run(['cc','-std=c99','-fsanitize=undefined,address','-g',str(p/'test.c'),'-o',str(p/'test')],check=True)
    subprocess.run([str(p/'test')],check=True)
subprocess.run(['python3',str(r/'tools/wayne/check-power-supply-properties.py')],check=True)
print('PASS: 40,146 current budgets, zero, subminimum, negative, I/O failure and suspended caching; both property layouts; invalid FCC/FV cache and I/O failure preservation')
