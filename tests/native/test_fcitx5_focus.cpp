#include <cassert>
#include <vector>
#include "../../native/fcitx5/focused_context.h"

struct Context {};
struct Manager {
    std::vector<Context *> focused;
    template <typename Visitor> void foreachFocused(Visitor visitor) {
        for (auto *context : focused) {
            if (!visitor(context)) break;
        }
    }
};
int main() {
    Context one, two;
    Manager none{};
    Manager single{{&one}};
    Manager multiple{{&one, &two}};
    assert(!inkecho_focus_selection<Context>(none).ambiguous);
    assert(inkecho_focus_selection<Context>(single).target == &one);
    assert(inkecho_focus_selection<Context>(multiple).target == nullptr);
    assert(inkecho_focus_selection<Context>(multiple).ambiguous);
    assert(inkecho_focus_rejection(inkecho_focus_selection<Context>(multiple), false) == 3);
    assert(inkecho_focus_rejection(inkecho_focus_selection<Context>(multiple), true) == 4);
    assert(inkecho_focus_rejection(inkecho_focus_selection<Context>(none), true) == 3);
    // The snapshot does not retain the previous target across a focus gap.
    single.focused.clear();
    assert(inkecho_focus_selection<Context>(single).target == nullptr);
    single.focused = {&two};
    assert(inkecho_focus_selection<Context>(single).target == &two);
    single.focused = {&one};
    assert(inkecho_unique_focus<Context>(none) == nullptr);
    assert(inkecho_unique_focus<Context>(single) == &one);
    assert(inkecho_unique_focus<Context>(multiple) == nullptr);
}
