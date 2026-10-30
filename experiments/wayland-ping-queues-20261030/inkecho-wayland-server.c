#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/socket.h>
#include <sys/wait.h>
#include <unistd.h>
#include <wayland-server.h>
#include "xdg-server.h"
#include "text-server.h"
static struct wl_display *display; static struct wl_resource *xdg,*text; static int ack; static struct wl_event_source *ready_source;
static void pong(struct wl_client *c,struct wl_resource *r,uint32_t serial) { (void)c;(void)r; assert(serial==42); puts("server_received_pong=42"); fflush(stdout); assert(write(ack,"P",1)==1); }
static const struct xdg_wm_base_interface xdgimpl={.pong=pong};
static void xdg_bind(struct wl_client*c,void*d,uint32_t ver,uint32_t id) {(void)d;(void)ver;xdg=wl_resource_create(c,&xdg_wm_base_interface,1,id);wl_resource_set_implementation(xdg,&xdgimpl,NULL,NULL);}
static void get_text(struct wl_client*c,struct wl_resource*r,uint32_t id,struct wl_resource*seat) {(void)r;(void)seat;text=wl_resource_create(c,&zwp_text_input_v3_interface,1,id);wl_resource_set_implementation(text,NULL,NULL,NULL);}
static const struct zwp_text_input_manager_v3_interface managerimpl={.get_text_input=get_text};
static void manager_bind(struct wl_client*c,void*d,uint32_t ver,uint32_t id) {(void)d;(void)ver;struct wl_resource*r=wl_resource_create(c,&zwp_text_input_manager_v3_interface,1,id);wl_resource_set_implementation(r,&managerimpl,NULL,NULL);}
static void seat_bind(struct wl_client*c,void*d,uint32_t ver,uint32_t id) {(void)d;(void)ver;struct wl_resource*r=wl_resource_create(c,&wl_seat_interface,1,id);wl_resource_set_implementation(r,NULL,NULL,NULL);wl_seat_send_capabilities(r,0);}
static int signal_ready(int fd,uint32_t mask,void*data) {(void)mask;(void)data;char ch;assert(read(fd,&ch,1)==1 && ch=='S');wl_event_source_remove(ready_source); ready_source=NULL; close(fd); assert(xdg && text);zwp_text_input_v3_send_commit_string(text,"A");zwp_text_input_v3_send_done(text,1);xdg_wm_base_send_ping(xdg,42);wl_display_flush_clients(display); puts("server_sent_commit_done_then_ping");fflush(stdout);return 0;}
int main(int argc,char**argv) {assert(argc==2);int pair[2],ready[2],back[2];assert(socketpair(AF_UNIX,SOCK_STREAM,0,pair)==0 && pipe(ready)==0 && pipe(back)==0);display=wl_display_create();assert(display);struct wl_event_loop*loop=wl_display_get_event_loop(display);assert(wl_global_create(display,&wl_seat_interface,1,NULL,seat_bind));assert(wl_global_create(display,&xdg_wm_base_interface,1,NULL,xdg_bind));assert(wl_global_create(display,&zwp_text_input_manager_v3_interface,1,NULL,manager_bind));assert(wl_client_create(display,pair[0]));ack=back[1];ready_source=wl_event_loop_add_fd(loop,ready[0],WL_EVENT_READABLE,signal_ready,NULL);assert(ready_source);pid_t pid=fork();assert(pid>=0);if(!pid){close(pair[0]);close(ready[0]);close(back[1]);char a[20],b[20],c[20];snprintf(a,sizeof(a),"%d",pair[1]);snprintf(b,sizeof(b),"%d",ready[1]);snprintf(c,sizeof(c),"%d",back[0]);execl(argv[1],argv[1],a,b,c,NULL);_exit(127);}close(pair[1]);close(ready[1]);close(back[0]);int status;for(;;){wl_event_loop_dispatch(loop,100);wl_display_flush_clients(display);if(waitpid(pid,&status,WNOHANG)==pid)break;}wl_display_destroy(display);return WIFEXITED(status)?WEXITSTATUS(status):1;}
