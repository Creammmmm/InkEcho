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
 FCITX_OBJECT_VTABLE_METHOD(preedit,"Preedit","b","u");
};
class Factory final: public AddonFactory { AddonInstance *create(AddonManager *m) override {return new Control(m->instance());}};
}
FCITX_ADDON_FACTORY(fcitx::Factory);
