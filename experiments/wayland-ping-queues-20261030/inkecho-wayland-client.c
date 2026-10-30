#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <wayland-client.h>
#include "xdg-client.h"
#include "text-client.h"
static struct xdg_wm_base*xdg;static struct wl_seat*seat;static struct zwp_text_input_manager_v3*mgr;static int commits,done;
static void global(void*d,struct wl_registry*r,uint32_t n,const char*i,uint32_t v){(void)d;(void)v;if(!strcmp(i,"xdg_wm_base"))xdg=wl_registry_bind(r,n,&xdg_wm_base_interface,1);if(!strcmp(i,"wl_seat"))seat=wl_registry_bind(r,n,&wl_seat_interface,1);if(!strcmp(i,"zwp_text_input_manager_v3"))mgr=wl_registry_bind(r,n,&zwp_text_input_manager_v3_interface,1);}
static void remove_g(void*d,struct wl_registry*r,uint32_t n){(void)d;(void)r;(void)n;} static const struct wl_registry_listener registry_listener={global,remove_g};
static void ping(void*d,struct xdg_wm_base*x,uint32_t serial){(void)d;assert(serial==42);xdg_wm_base_pong(x,serial);}
static const struct xdg_wm_base_listener xdg_listener={ping};
static void enter(void*d,struct zwp_text_input_v3*t,struct wl_surface*s){(void)d;(void)t;(void)s;} static void leave(void*d,struct zwp_text_input_v3*t,struct wl_surface*s){(void)d;(void)t;(void)s;} static void pre(void*d,struct zwp_text_input_v3*t,const char*s,int32_t a,int32_t b){(void)d;(void)t;(void)s;(void)a;(void)b;} static void commit(void*d,struct zwp_text_input_v3*t,const char*s){(void)d;(void)t;assert(!strcmp(s,"A"));commits++;} static void del(void*d,struct zwp_text_input_v3*t,uint32_t a,uint32_t b){(void)d;(void)t;(void)a;(void)b;} static void done_cb(void*d,struct zwp_text_input_v3*t,uint32_t serial){(void)d;(void)t;assert(serial==1);done++;} static const struct zwp_text_input_v3_listener text_listener={enter,leave,pre,commit,del,done_cb};
int main(int argc,char**argv){assert(argc==4);int fd=atoi(argv[1]),ready=atoi(argv[2]),ack=atoi(argv[3]);struct wl_display*d=wl_display_connect_to_fd(fd);assert(d);struct wl_registry*r=wl_display_get_registry(d);wl_registry_add_listener(r,&registry_listener,NULL);assert(wl_display_roundtrip(d)>=0 && xdg && seat && mgr);struct wl_event_queue*qping=wl_display_create_queue(d),*qtext=wl_display_create_queue(d);wl_proxy_set_queue((struct wl_proxy*)xdg,qping);xdg_wm_base_add_listener(xdg,&xdg_listener,NULL);struct zwp_text_input_v3*t=zwp_text_input_manager_v3_get_text_input(mgr,seat);wl_proxy_set_queue((struct wl_proxy*)t,qtext);zwp_text_input_v3_add_listener(t,&text_listener,NULL);assert(wl_display_roundtrip(d)>=0);assert(write(ready,"S",1)==1);assert(wl_display_dispatch_queue(d,qping)>=0);assert(wl_display_flush(d)>=0);char c;assert(read(ack,&c,1)==1 && c=='P');printf("after_server_pong commit=%d done=%d\n",commits,done);fflush(stdout);assert(commits==0 && done==0);assert(wl_display_dispatch_queue_pending(d,qtext)>=0);printf("after_text_queue commit=%d done=%d\n",commits,done);fflush(stdout);assert(commits==1 && done==1);wl_display_disconnect(d);return 0;}
