#define _POSIX_C_SOURCE 200809L
#include <xcb/xcb.h>
#include <xcb-imdkit/imdkit.h>
#include <xcb-imdkit/imclient.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

static xcb_connection_t *server_conn, *client_conn;
static xcb_im_t *server;
static xcb_xim_t *client;
static xcb_im_input_context_t *server_ic;
static xcb_xic_t client_ic;
static int created, commits, syncs, client_syncs, stop_after_commit;
static xcb_window_t client_window;

static void server_cb(xcb_im_t *im, xcb_im_client_t *cl, xcb_im_input_context_t *ic,
                      const xcb_im_packet_header_fr_t *hdr, void *frame, void *arg, void *user) {
    (void)im;(void)cl;(void)frame;(void)arg;(void)user;
    if (hdr->major_opcode == XCB_XIM_CREATE_IC) server_ic = ic;
    if (hdr->major_opcode == XCB_XIM_SYNC_REPLY) syncs++;
}
static void create_cb(xcb_xim_t *im, xcb_xic_t ic, void *user) {
    (void)im;(void)user; client_ic = ic; created = 1;
}
static void open_cb(xcb_xim_t *im, void *user) {
    (void)user; uint32_t style = XCB_IM_PreeditNothing | XCB_IM_StatusNothing;
    if (!xcb_xim_create_ic(im, create_cb, NULL, XCB_XIM_XNInputStyle, &style,
                           XCB_XIM_XNClientWindow, &client_window,
                           XCB_XIM_XNFocusWindow, &client_window, NULL)) abort();
}
static void commit_cb(xcb_xim_t *im, xcb_xic_t ic, uint32_t flag, char *str,
                      uint32_t length, uint32_t *keys, size_t nkeys, void *user) {
    (void)im;(void)flag;(void)keys;(void)nkeys;(void)user;
    if (ic != client_ic || length != 1 || memcmp(str, "A", 1)) abort();
    commits++;
}
static void sync_cb(xcb_xim_t *im, xcb_xic_t ic, void *user) {
    (void)im;(void)ic;(void)user; client_syncs++;
}
static long ms(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec*1000L+t.tv_nsec/1000000L; }
static void drain(xcb_connection_t *c, int is_server) {
    if (!is_server && stop_after_commit && commits) return;
    xcb_generic_event_t *ev;
    while ((ev=xcb_poll_for_event(c))) {
        if (is_server) xcb_im_filter_event(server, ev);
        else xcb_xim_filter_event(client, ev);
        free(ev);
        if (!is_server && stop_after_commit && commits) break;
    }
}
int main(void) {
    int sn=0,cn=0; server_conn=xcb_connect(NULL,&sn); client_conn=xcb_connect(NULL,&cn);
    if (xcb_connection_has_error(server_conn)||xcb_connection_has_error(client_conn)) return 2;
    xcb_screen_t *ss=xcb_setup_roots_iterator(xcb_get_setup(server_conn)).data;
    xcb_screen_t *cs=xcb_setup_roots_iterator(xcb_get_setup(client_conn)).data;
    xcb_window_t sw=xcb_generate_id(server_conn); client_window=xcb_generate_id(client_conn);
    xcb_create_window(server_conn,XCB_COPY_FROM_PARENT,sw,ss->root,0,0,1,1,0,XCB_WINDOW_CLASS_INPUT_OUTPUT,ss->root_visual,0,NULL);
    xcb_create_window(client_conn,XCB_COPY_FROM_PARENT,client_window,cs->root,0,0,1,1,0,XCB_WINDOW_CLASS_INPUT_OUTPUT,cs->root_visual,0,NULL);
    uint32_t styles_data[]={XCB_IM_PreeditNothing|XCB_IM_StatusNothing};
    xcb_im_styles_t styles={1,styles_data}; char *encoding_data[]={"COMPOUND_TEXT"};
    xcb_im_encodings_t encodings={1,encoding_data};
    server=xcb_im_create(server_conn,sn,sw,"inkecho-test",XCB_IM_ALL_LOCALES,&styles,NULL,NULL,&encodings,0,server_cb,NULL);
    if (!server || !xcb_im_open_im(server)) return 3;
    xcb_flush(server_conn);
    client=xcb_xim_create(client_conn,cn,"@im=inkecho-test");
    xcb_xim_im_callback callbacks={0};callbacks.commit_string=commit_cb;callbacks.sync=sync_cb;
    xcb_xim_set_im_callback(client,&callbacks,NULL);
    if (!xcb_xim_open(client,open_cb,true,NULL)) return 4;
    long deadline=ms()+5000;
    while ((!created||!server_ic)&&ms()<deadline) { drain(server_conn,1);drain(client_conn,0);xcb_flush(server_conn);xcb_flush(client_conn);struct timespec t={0,1000000};nanosleep(&t,NULL); }
    if (!created||!server_ic) {fprintf(stderr,"context unavailable\n");return 5;}
    xcb_im_commit_string(server,server_ic,XCB_XIM_LOOKUP_CHARS,"A",1,0);
    xcb_im_sync_xlib(server,server_ic);xcb_flush(server_conn);
    long until=ms()+400;
    while (ms()<until) {drain(server_conn,1);xcb_flush(server_conn);struct timespec t={0,1000000};nanosleep(&t,NULL);}
    printf("paused: commits=%d sync_replies=%d\n",commits,syncs);
    if (commits||syncs) return 6;
    stop_after_commit = 1;
    deadline=ms()+5000;
    while ((!commits||!syncs)&&ms()<deadline) {drain(client_conn,0);xcb_flush(client_conn);drain(server_conn,1);xcb_flush(server_conn);struct timespec t={0,1000000};nanosleep(&t,NULL);}
    printf("first reply: commits=%d sync_replies=%d client_sync_requests=%d\n",commits,syncs,client_syncs);
    if (commits!=1 || syncs!=1 || client_syncs!=0) return 7;
    stop_after_commit = 0;
    deadline=ms()+1000;
    while (!client_syncs && ms()<deadline) {drain(client_conn,0);xcb_flush(client_conn);drain(server_conn,1);xcb_flush(server_conn);struct timespec t={0,1000000};nanosleep(&t,NULL);}
    printf("final: commits=%d sync_replies=%d client_sync_requests=%d\n",commits,syncs,client_syncs);
    return 0;
}
