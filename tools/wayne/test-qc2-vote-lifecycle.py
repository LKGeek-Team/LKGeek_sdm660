#!/usr/bin/env python3
"""Run actual legacy/PD handlers against a mock min-vote engine."""
from pathlib import Path
import re, subprocess, tempfile
root=Path(__file__).resolve().parents[2]
s=(root/'drivers/power/supply/qcom/smb-lib.c').read_text()
h=(root/'drivers/power/supply/qcom/smb-lib.h').read_text()
def function(marker):
 a=s.index(marker);b=s.index('{',a);depth=1;e=b+1
 while depth:
  depth+=(s[e]=='{')-(s[e]=='}');e+=1
 return s[a:e]
legacy=function('static void smblib_force_legacy_icl(')
pd=function('static int __smblib_set_prop_pd_active(')
removal=function('static void smblib_handle_typec_removal(')
a=removal.index('/* reset input current limit voters */');b=removal.index('/* reset hvdcp voters */')
reset=removal[a:b]
assert 'USER_VOTER' not in legacy and 'USER_VOTER' not in reset
uusb=function('static void smblib_uusb_removal(')
assert 'vote(chg->usb_icl_votable, LEGACY_HVDCP_VOTER, false, 0);' in uusb
voters=dict(re.findall(r'#define\s+(\w+_VOTER)\s+"([^"]+)"',h))
prefix='''#include <assert.h>
#include <stdbool.h>
#include <string.h>
#include <limits.h>
typedef unsigned char u8;
static int usb,other;
struct smb_charger { bool pd_active,typec_legacy_valid;int real_charger_type,connector_type;u8 typec_status[4];int legacy_detection_work;void *usb_icl_votable,*apsd_disable_votable,*pd_allowed_votable,*usb_irq_enable_votable,*hvdcp_disable_votable_indirect,*usb_psy;};
struct entry {const char *name;bool enabled;int value;} entries[64];int count;
static int vote(void *v,const char *n,bool on,int value) {if(v!=&usb)return 0;int i;for(i=0;i<count;i++)if(!strcmp(entries[i].name,n))break;if(i==count)entries[count++].name=n;entries[i].enabled=on;entries[i].value=value;return 0;}
static bool is_client_vote_enabled(void *v,const char *n) {for(int i=0;i<count;i++)if(!strcmp(entries[i].name,n))return entries[i].enabled;return false;}
static int effective(void) {int out=INT_MAX;for(int i=0;i<count;i++)if(entries[i].enabled && entries[i].value<out)out=entries[i].value;return out;}
#define smblib_err(...) ((void)0)
static int smblib_get_prop_typec_mode(struct smb_charger *c) {return 0;}
static int get_rp_based_dcp_current(struct smb_charger *c,int t) {return 2500000;}
static int smblib_masked_write(struct smb_charger *c,int r,int m,int v) {return 0;}
static int smblib_read(struct smb_charger *c,int r,u8 *v) {*v=0;return 0;}
static void schedule_work(int *w) {}
static void smblib_update_usb_type(struct smb_charger *c) {}
static void power_supply_changed(void *p) {}
#define CONFIG_QCOM_LONGCHEER_CHARGER_POLICY 1
#define CONFIG_QCOM_LONGCHEER_WAYNE_CHARGER_POLICY 1
#define USBIN_500MA 500000
#define HVDCP2_CURRENT_UA 2000000
#define HVDCP_CURRENT_UA 3000000
#define CDP_CURRENT_UA 2000000
'''
for k,v in voters.items():prefix+=f'#define {k} "{v}"\n'
known=set(re.findall(r'#define\s+(\w+)',prefix))|{'INT_MAX'}
for i,k in enumerate(sorted(set(re.findall(r'\b[A-Z][A-Z0-9_]+\b',legacy+pd+reset))-known)):
 if k.startswith('CONFIG_'):continue
 # Uppercase words in comments do not affect compilation.
 prefix+=f'#define {k} {100+i}\n'
main='''
int main(void) {
 struct smb_charger obj={.usb_icl_votable=&usb,.apsd_disable_votable=&other,.pd_allowed_votable=&other,.usb_irq_enable_votable=&other,.hvdcp_disable_votable_indirect=&other},*chg=&obj;
 smblib_force_legacy_icl(chg,POWER_SUPPLY_TYPE_USB_HVDCP);assert(effective()==2000000);assert(!is_client_vote_enabled(&usb,USER_VOTER));
 vote(&usb,USER_VOTER,true,0);
 smblib_force_legacy_icl(chg,POWER_SUPPLY_TYPE_USB_CDP);assert(effective()==0);assert(!is_client_vote_enabled(&usb,LEGACY_HVDCP_VOTER));
 assert(!__smblib_set_prop_pd_active(chg,true));assert(effective()==0);assert(is_client_vote_enabled(&usb,USER_VOTER));
 vote(&usb,USER_VOTER,false,0);assert(effective()==500000);vote(&usb,PD_VOTER,true,3000000);assert(effective()==3000000);
 chg->pd_active=false;smblib_force_legacy_icl(chg,POWER_SUPPLY_TYPE_USB_HVDCP);assert(effective()==2000000);
 assert(!__smblib_set_prop_pd_active(chg,true));assert(!is_client_vote_enabled(&usb,LEGACY_HVDCP_VOTER));assert(effective()==500000);
 vote(&usb,PD_VOTER,true,3000000);assert(effective()==3000000);
 vote(&usb,BOARD_ICL_VOTER,true,2900000);vote(&usb,PD_VOTER,true,5100000);assert(effective()==2900000);
 vote(&usb,THERMAL_DAEMON_VOTER,true,1000000);assert(effective()==1000000);
 vote(&usb,USER_VOTER,true,0);assert(effective()==0);vote(&usb,USER_VOTER,false,0);
 vote(&usb,THERMAL_DAEMON_VOTER,false,0);assert(effective()==2900000);vote(&usb,BOARD_ICL_VOTER,false,0);
 chg->pd_active=false;smblib_force_legacy_icl(chg,POWER_SUPPLY_TYPE_USB_HVDCP);
 vote(&usb,USER_VOTER,true,0);reset_votes(chg);assert(!is_client_vote_enabled(&usb,LEGACY_HVDCP_VOTER));assert(is_client_vote_enabled(&usb,USER_VOTER));assert(effective()==0);
 return 0;
}
'''
with tempfile.TemporaryDirectory()as td:
 p=Path(td);(p/'test.c').write_text(prefix+legacy+'\n'+pd+'\nstatic void reset_votes(struct smb_charger *chg) {\n'+reset+'\n}\n'+main)
 subprocess.run(['cc','-std=c99','-fsanitize=undefined,address',str(p/'test.c'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
print('PASS: QC2 2A, QC2->CDP/PD/detach cleanup, PD 500mA handoff and negotiated limit, USER suspend survives transitions')
