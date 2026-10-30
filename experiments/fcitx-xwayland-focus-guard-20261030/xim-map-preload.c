#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdint.h>
#include <stddef.h>
typedef void (*free_fn)(void *);
typedef void (*set_fn)(void *, void *, free_fn);
typedef uint32_t (*get_window_fn)(void *);
static struct {void *ic;void *context;} entries[64];
static void *symbol(const char *name) {
 void *handle=dlopen("libxcb-imdkit.so.1",RTLD_NOW|RTLD_NOLOAD);
 return handle?dlsym(handle,name):NULL;
}
void xcb_im_input_context_set_data(void *ic, void *context, free_fn free_data) {
 static set_fn real;
 if(!real) real=(set_fn)symbol("xcb_im_input_context_set_data");
 if(!real) __builtin_trap();
 for(size_t i=0;i<64;i++) if(entries[i].ic==ic || (!entries[i].ic && context)) {entries[i].ic=context?ic:NULL;entries[i].context=context;break;}
 real(ic,context,free_data);
}
uint32_t inkecho_test_xim_window(void *context) {
 for(size_t i=0;i<64;i++) if(entries[i].context==context && entries[i].ic) {
  get_window_fn focus=(get_window_fn)symbol("xcb_im_input_context_get_focus_window");
  get_window_fn client=(get_window_fn)symbol("xcb_im_input_context_get_client_window");
  if(!focus || !client)return 0;
  uint32_t result=focus(entries[i].ic);return result?result:client(entries[i].ic);
 }
 return 0;
}
