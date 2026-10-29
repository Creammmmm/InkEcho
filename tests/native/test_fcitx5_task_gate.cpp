// SPDX-License-Identifier: MIT
#include "../../native/fcitx5/task_gate.h"
#include <cassert>
#include <fstream>
#include <stdexcept>
#include <string>

int main() {
    char root[] = "/tmp/inkecho-task-gate-XXXXXX";
    assert(mkdtemp(root));
    assert(setenv("XDG_RUNTIME_DIR", root, 1) == 0);
    const std::string file = std::string(root) + "/inkecho-fcitx-candidate.cap";
    const std::string token(64, 'a');
    auto write = [&] { std::ofstream stream(file); stream << token; stream.close(); assert(chmod(file.c_str(),0600)==0); };
    write();
    inkecho::TaskGate gate;
    assert(!gate.begin(":1.2", std::string(64,'b')));
    assert(gate.begin(":1.1", token));
    assert(access(file.c_str(), F_OK) != 0);
    int sent=0;
    auto deliver = [&](const std::string&) { ++sent; return true; };
    assert(!gate.commit(":1.2", token, 0, "甲", deliver));
    assert(!gate.commit(":1.1", token, 1, "甲", deliver));
    assert(gate.commit(":1.1", token, 0, "甲", deliver));
    assert(!gate.commit(":1.1", token, 0, "甲", deliver));
    assert(gate.cancel(":1.1", token));
    assert(!gate.commit(":1.1", token, 1, "乙", deliver));
    assert(!gate.begin(":1.1", token));
    assert(sent==1);
    write();
    inkecho::TaskGate switching;
    assert(switching.begin(":1.1", token));
    auto missing = [&](const std::string&) { return false; };
    assert(switching.commit(":1.1", token, 0, "甲", missing) == 3);
    assert(switching.commit(":1.1", token, 0, "甲", missing) == 3);
    assert(sent == 1);
    assert(switching.commit(":1.1", token, 0, "甲", deliver) == 1);
    assert(switching.commit(":1.1", token, 0, "甲", deliver) == 0);
    assert(switching.cancel(":1.1", token));
    assert(sent == 2);
    write();
    inkecho::TaskGate ambiguous;
    assert(ambiguous.begin(":1.1", token));
    auto fail = [&](const std::string&) -> bool { ++sent; throw std::runtime_error("private"); };
    assert(ambiguous.commit(":1.1", token, 0, "甲", fail) == 2);
    assert(sent == 3);
    assert(!ambiguous.commit(":1.1", token, 0, "甲", deliver));
    write();
    assert(chmod(file.c_str(), 0644)==0);
    inkecho::TaskGate unsafe;
    assert(!unsafe.begin(":1.1", token));
    assert(unlink(file.c_str())==0);
    assert(symlink("/etc/passwd", file.c_str())==0);
    assert(!unsafe.begin(":1.1", token));
    assert(unlink(file.c_str())==0);
    assert(rmdir(root)==0);
}
