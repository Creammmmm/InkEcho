#include <stdio.h>
#include <stdlib.h>
#include <xcb/xcb.h>
#include <xcb/res.h>
int main(int argc,char **argv) {
 if(argc != 3) return 2;
 int screen=0; xcb_connection_t*c=xcb_connect(NULL,&screen);
 if(xcb_connection_has_error(c))return 3;
 for(int i=1;i<argc;i++) {
  xcb_res_client_id_spec_t spec={(uint32_t)strtoul(argv[i],NULL,0),XCB_RES_CLIENT_ID_MASK_LOCAL_CLIENT_PID};
  xcb_res_query_client_ids_reply_t*r=xcb_res_query_client_ids_reply(c,xcb_res_query_client_ids(c,1,&spec),NULL);
  if(!r)return 4;
  xcb_res_client_id_value_iterator_t it=xcb_res_query_client_ids_ids_iterator(r);unsigned pid=0;
  for(;it.rem;xcb_res_client_id_value_next(&it)) if(it.data->spec.mask & XCB_RES_CLIENT_ID_MASK_LOCAL_CLIENT_PID) {if(xcb_res_client_id_value_value_length(it.data)!=1)return 5;pid=*xcb_res_client_id_value_value(it.data);}
  printf("%u%c",pid,i==argc-1?'\n':' ');free(r);
 }
 xcb_disconnect(c);return 0;
}
