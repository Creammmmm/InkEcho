#include <cassert>
#include <initializer_list>
#include "../../native/fcitx5/focused_context.h"

struct Panel {
    bool preedit = false, client = false, candidates = false, aux = false;
    bool empty() const { return !preedit && !client && !candidates && !aux; }
};
struct Context {
    Panel panel;
    bool pending = false;
    unsigned attempts = 0;
    const Panel &inputPanel() const { return panel; }
    bool hasPendingEvents() const { return pending; }
};
int main() {
    Context context;
    assert(!inkecho_composition_blocked(context));
    // Each state is checked independently; no reset/flush/commit is allowed.
    for (bool *state : {&context.panel.preedit, &context.panel.client,
                       &context.panel.candidates, &context.panel.aux, &context.pending}) {
        *state = true;
        assert(inkecho_composition_blocked(context));
        assert(*state && context.attempts == 0);
        *state = false;
        assert(!inkecho_composition_blocked(context));
    }
}
