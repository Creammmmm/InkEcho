// Isolated protocol fixture only; never installed into a user's Fcitx session.
#include <memory>
#include <fcitx-utils/dbus/bus.h>
#include <fcitx-utils/dbus/objectvtable.h>
#include <fcitx/addonfactory.h>
#include <fcitx/addoninstance.h>
#include <fcitx/addonmanager.h>
#include <fcitx/inputcontext.h>
#include <fcitx/inputcontextmanager.h>
#include <fcitx/inputpanel.h>
#include <fcitx/focusgroup.h>
#include <fcitx/instance.h>
#include <fcitx-module/dbus/dbus_public.h>
namespace fcitx {
class OwnedContext final : public InputContext {
public:
 explicit OwnedContext(InputContextManager &m) : InputContext(m, "inkecho-owned-protocol-fixture") { created(); setCapabilityFlags(CapabilityFlag::Preedit); }
 ~OwnedContext() override { destroy(); }
 const char *frontend() const override { return "inkecho-owned-test"; }
 std::uint32_t delivered = 0;
protected:
 void commitStringImpl(const std::string &) override { ++delivered; }
 void deleteSurroundingTextImpl(int, unsigned int) override {}
 void forwardKeyImpl(const ForwardKeyEvent &) override {}
 void updatePreeditImpl() override {}
};
class Control final : public AddonInstance, public dbus::ObjectVTable<Control> {
public:
 explicit Control(Instance *instance) : instance_(instance),
  aGroup_(std::make_unique<FocusGroup>("inkecho-owned:A", instance->inputContextManager())),
  bGroup_(std::make_unique<FocusGroup>("inkecho-owned:B", instance->inputContextManager())),
  a_(new OwnedContext(instance->inputContextManager())), b_(new OwnedContext(instance->inputContextManager())) {
  a_->setFocusGroup(aGroup_.get()); b_->setFocusGroup(bGroup_.get());
  auto *module=instance->addonManager().addon("dbus",true);
  if (module) { auto *bus=module->call<IDBusModule::bus>();
   if(bus) bus->addObjectVTable("/ownedtest", "org.fcitx.Fcitx.OwnedTest1", *this);
  }
 }
 std::uint32_t focus(std::uint32_t mode) {
  a_->focusOut(); b_->focusOut();
  if(mode==1 || mode==2) a_->focusIn();
  if(mode==2 || mode==3) b_->focusIn();
  std::uint32_t count=0;
  instance_->inputContextManager().foreachFocused([&](InputContext *){++count;return true;});
  return count;
 }
 std::uint32_t state(std::uint32_t mode) {
  if (blocked_) { a_->setBlockEventToClient(false); blocked_=false; }
  a_->inputPanel().reset();
  if(mode==1) a_->inputPanel().setPreedit(Text("owned-fixture"));
  if(mode==2) a_->inputPanel().setClientPreedit(Text("owned-fixture"));
  if(mode==3) a_->inputPanel().setAuxUp(Text("owned-fixture"));
  if(mode==4) a_->inputPanel().setAuxDown(Text("owned-fixture"));
  if(mode==5) { a_->setBlockEventToClient(true); blocked_=true; a_->inputPanel().setClientPreedit(Text("owned-fixture")); a_->updatePreedit(); a_->inputPanel().reset(); a_->updatePreedit(); }
  return stateBits();
 }
 std::uint32_t stateBits(){return (!a_->inputPanel().empty()?1:0) | (a_->hasPendingEvents()?2:0);}
 std::uint32_t countA(){return a_->delivered;}
 std::uint32_t countB(){return b_->delivered;}
 bool quit(){delete a_; a_=nullptr; delete b_; b_=nullptr; aGroup_.reset(); bGroup_.reset(); instance_->exit();return true;}
 FCITX_OBJECT_VTABLE_METHOD(focus,"Focus","u","u");
 FCITX_OBJECT_VTABLE_METHOD(state,"State","u","u");
 FCITX_OBJECT_VTABLE_METHOD(stateBits,"StateBits","","u");
 FCITX_OBJECT_VTABLE_METHOD(countA,"CountA","","u");
 FCITX_OBJECT_VTABLE_METHOD(countB,"CountB","","u");
 FCITX_OBJECT_VTABLE_METHOD(quit,"Quit","","b");
private:
 bool blocked_ = false;
 Instance *instance_; std::unique_ptr<FocusGroup> aGroup_, bGroup_; OwnedContext *a_, *b_;
};
class Factory final : public AddonFactory {
 AddonInstance *create(AddonManager *manager) override{return new Control(manager->instance());}
};
}
FCITX_ADDON_FACTORY(fcitx::Factory);
