// SPDX-License-Identifier: MIT
// Fcitx5 addon: submit only to the currently focused input context.
#include <string>

#include <fcitx-utils/dbus/bus.h>
#include <fcitx-utils/dbus/message.h>
#include <fcitx-utils/dbus/objectvtable.h>
#include <fcitx-utils/dbus/servicewatcher.h>
#include <fcitx/addonfactory.h>
#include <fcitx/addoninstance.h>
#include <fcitx/addonmanager.h>
#include <fcitx/inputcontext.h>
#include <fcitx/inputcontextmanager.h>
#include <fcitx/instance.h>
#include <fcitx-module/dbus/dbus_public.h>

#include "focused_context.h"
#include "task_gate.h"

namespace fcitx {
class InkEcho final : public AddonInstance, public dbus::ObjectVTable<InkEcho> {
public:
    explicit InkEcho(Instance *instance) : instance_(instance) {
        auto *module = instance_->addonManager().addon("dbus", true);
        if (module) {
            auto *bus = module->call<IDBusModule::bus>();
            if (bus) {
                watcher_ = std::make_unique<dbus::ServiceWatcher>(*bus);
                bus->addObjectVTable("/inkecho", "org.fcitx.Fcitx.InkEcho1", *this);
            }
        }
    }

    std::string sender() const {
        auto *message = currentMessage();
        return message ? message->sender() : "";
    }

    bool beginTask(const std::string &token, bool detailedFocus) {
        const auto owner = sender();
        if (!watcher_ || !gate_.begin(owner, token)) return false;
        detailedFocus_ = detailedFocus;
        watch_ = watcher_->watchService(owner, [this, token](const std::string &name, const std::string &, const std::string &newOwner) {
            if (newOwner.empty()) gate_.owner_lost(name, token);
        });
        if (!watch_) { gate_.owner_lost(owner, token); return false; }
        return true;
    }
    bool begin(const std::string &token) { return beginTask(token, false); }
    bool begin2(const std::string &token, std::uint32_t version) {
        return version == 2 && beginTask(token, true);
    }
    bool cancel(const std::string &token) { return gate_.cancel(sender(), token); }
    std::string runtimeVersion() { return Instance::version(); }
    std::uint32_t commit(const std::string &token, std::uint32_t sequence, const std::string &text) {
        std::uint32_t rejected = 3;
        const auto result = gate_.commit(sender(), token, sequence, text, [this, &rejected](const std::string &scalar) {
            const auto selection = inkecho_focus_selection<InputContext>(instance_->inputContextManager());
            if (!selection.target) {
                rejected = inkecho_focus_rejection(selection, detailedFocus_);
                return false;
            }
            // This is an attempt, not acknowledgement from the target client.
            selection.target->commitString(scalar);
            return true;
        });
        return result == 3 ? rejected : result;
    }

    FCITX_OBJECT_VTABLE_METHOD(begin, "Begin", "s", "b");
    FCITX_OBJECT_VTABLE_METHOD(begin2, "Begin2", "su", "b");
    FCITX_OBJECT_VTABLE_METHOD(cancel, "Cancel", "s", "b");
    FCITX_OBJECT_VTABLE_METHOD(runtimeVersion, "RuntimeVersion", "", "s");
    FCITX_OBJECT_VTABLE_METHOD(commit, "Commit", "sus", "u");

private:
    Instance *instance_;
    inkecho::TaskGate gate_;
    bool detailedFocus_ = false;
    std::unique_ptr<dbus::ServiceWatcher> watcher_;
    std::unique_ptr<dbus::ServiceWatcherEntry> watch_;
};

class Factory final : public AddonFactory {
public:
    AddonInstance *create(AddonManager *manager) override {
        return new InkEcho(manager->instance());
    }
};
} // namespace fcitx

FCITX_ADDON_FACTORY(fcitx::Factory);
