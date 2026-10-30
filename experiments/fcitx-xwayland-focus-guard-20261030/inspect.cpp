#include <dlfcn.h>
#include <cstdlib>
#include <xcb/xcb.h>
#include <xcb/res.h>
#include <fcitx-utils/dbus/bus.h>
#include <fcitx-utils/dbus/objectvtable.h>
#include <fcitx/addonfactory.h>
#include <fcitx/addoninstance.h>
#include <fcitx/addonmanager.h>
#include <fcitx/inputcontext.h>
#include <fcitx/inputcontextmanager.h>
#include <fcitx/inputpanel.h>
#include <fcitx/instance.h>
#include <fcitx-module/dbus/dbus_public.h>
namespace fcitx {
class Control final: public AddonInstance, public dbus::ObjectVTable<Control> {
 Instance *instance_;
 public:
 explicit Control(Instance *i): instance_(i) {auto *m=i->addonManager().addon("dbus",true); if(m) m->call<IDBusModule::bus>()->addObjectVTable("/inkecho_test", "org.fcitx.Fcitx.TestOnly", *this);}
 std::uint32_t preedit(bool enable) {InputContext *ctx=nullptr; unsigned count=0; instance_->inputContextManager().foreachFocused([&](InputContext *c){ctx=c;++count;return true;}); if(count!=1)return 0; ctx->inputPanel().reset(); if(enable)ctx->inputPanel().setClientPreedit(Text("owned-test"));ctx->updatePreedit(); return ctx->inputPanel().empty()?1:2;}
 std::string focusedInfo() {InputContext *ctx=nullptr; unsigned count=0; instance_->inputContextManager().foreachFocused([&](InputContext *c){ctx=c;++count;return true;}); if(count!=1)return "ambiguous"; return ctx->frontendName().data()+std::string("|")+ctx->program()+"|"+ctx->display();}
 std::uint32_t ximWindow() {InputContext *ctx=nullptr; unsigned count=0; instance_->inputContextManager().foreachFocused([&](InputContext *c){ctx=c;++count;return true;}); if(count!=1 || ctx->frontendName()!="xim")return 0; auto *fn=reinterpret_cast<std::uint32_t (*)(void*)>(dlsym(RTLD_DEFAULT,"inkecho_test_xim_window"));return fn?fn(ctx):0;}
 std::uint32_t guardedProbe() {
  auto old=ximWindow(); if(!old) return 2;
  int screen=0;auto *conn=xcb_connect(nullptr,&screen); if(xcb_connection_has_error(conn)){xcb_disconnect(conn);return 2;}
  auto *focus=xcb_get_input_focus_reply(conn,xcb_get_input_focus(conn),nullptr);
  if(!focus){xcb_disconnect(conn);return 2;} auto current=focus->focus;free(focus);
  auto pid=[&](std::uint32_t xid){xcb_res_client_id_spec_t spec{xid,XCB_RES_CLIENT_ID_MASK_LOCAL_CLIENT_PID};auto *r=xcb_res_query_client_ids_reply(conn,xcb_res_query_client_ids(conn,1,&spec),nullptr);std::uint32_t p=0;if(r){for(auto it=xcb_res_query_client_ids_ids_iterator(r);it.rem;xcb_res_client_id_value_next(&it)){if((it.data->spec.mask & XCB_RES_CLIENT_ID_MASK_LOCAL_CLIENT_PID) && xcb_res_client_id_value_value_length(it.data)==1)p=*xcb_res_client_id_value_value(it.data);}free(r);}return p;};
  auto a=pid(old),b=pid(current);xcb_disconnect(conn);if(!a || !b)return 2;return a==b?1:0;
 }
 std::uint32_t ancestorProbe() {
  auto old=ximWindow(); if(!old)return 2;int screen=0;auto*c=xcb_connect(nullptr,&screen);if(xcb_connection_has_error(c)){xcb_disconnect(c);return 2;}
  auto*f=xcb_get_input_focus_reply(c,xcb_get_input_focus(c),nullptr);if(!f){xcb_disconnect(c);return 2;}auto current=f->focus;free(f);
  auto top=[&](std::uint32_t w){for(unsigned i=0;i<64 && w>1;i++){auto*r=xcb_query_tree_reply(c,xcb_query_tree(c,w),nullptr);if(!r)return std::uint32_t(0);auto parent=r->parent,root=r->root;free(r);if(parent==root)return w;if(!parent || parent==w)return std::uint32_t(0);w=parent;}return std::uint32_t(0);};
  auto a=top(old),b=top(current);xcb_disconnect(c);if(!a || !b)return 2;return a==b?1:0;
 }
 FCITX_OBJECT_VTABLE_METHOD(ancestorProbe,"AncestorProbe","","u");
 FCITX_OBJECT_VTABLE_METHOD(guardedProbe,"GuardedProbe","","u");
 FCITX_OBJECT_VTABLE_METHOD(ximWindow,"XimWindow","","u");
 FCITX_OBJECT_VTABLE_METHOD(focusedInfo,"FocusedInfo","","s");
 FCITX_OBJECT_VTABLE_METHOD(preedit,"Preedit","b","u");
};
class Factory final: public AddonFactory { AddonInstance *create(AddonManager *m) override {return new Control(m->instance());}};
}
FCITX_ADDON_FACTORY(fcitx::Factory);
