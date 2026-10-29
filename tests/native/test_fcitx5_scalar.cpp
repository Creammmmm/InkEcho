#include <cassert>
#include <string_view>
#include "../../native/fcitx5/utf8_scalar.h"

int main() {
    assert(inkecho_one_scalar("a"));
    assert(inkecho_one_scalar("中"));
    assert(inkecho_one_scalar("😀"));
    assert(!inkecho_one_scalar(""));
    assert(!inkecho_one_scalar("ab"));
    assert(!inkecho_one_scalar(std::string_view("\0", 1)));
    assert(inkecho_one_scalar("\n"));
    assert(inkecho_one_scalar("\t"));
    assert(!inkecho_one_scalar("\r"));
    assert(!inkecho_one_scalar("\x7f"));
    assert(!inkecho_one_scalar("\xc2\x80"));
    assert(!inkecho_one_scalar("\xc0\x80"));
    assert(!inkecho_one_scalar("\xe0\x80\x80"));
    assert(!inkecho_one_scalar("\xed\xa0\x80"));
    assert(!inkecho_one_scalar("\xf4\x90\x80\x80"));
    assert(!inkecho_one_scalar("\xf0\x9f\x98"));
    assert(!inkecho_one_scalar("\xe4\xb8" "a"));
}
