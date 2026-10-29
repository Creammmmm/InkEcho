// SPDX-License-Identifier: MIT
#include "capability_gate.h"
#include <cassert>
#include <fstream>
#include <stdexcept>
#include <string>
#include <sys/stat.h>
#include <unistd.h>

using namespace inkecho_experiment;
int main() {
    char directory[] = "/tmp/inkecho-auth-test-XXXXXX";
    assert(mkdtemp(directory));
    const std::string root = directory, file = root + "/inkecho-fcitx-candidate.cap";
    const std::string token(64, 'a'), wrong(64, 'b');
    { std::ofstream out(file); out << token; }
    assert(chmod(file.c_str(), 0600) == 0);
    assert(capability_matches(root, token));
    assert(!capability_matches(root, wrong));
    auto until = Gate::Clock::now() + std::chrono::minutes(1);
    Gate gate(root);
    assert(!gate.begin(":1.1", wrong, until));
    assert(gate.begin(":1.1", token, until));
    int delivered = 0;
    auto send = [&](const std::string &) { ++delivered; return true; };
    assert(!gate.commit(":1.2", token, 0, "中", send));
    assert(!gate.commit(":1.1", wrong, 0, "中", send));
    assert(!gate.commit(":1.1", token, 1, "中", send));
    assert(gate.commit(":1.1", token, 0, "中", send));
    assert(!gate.commit(":1.1", token, 0, "中", send));
    assert(gate.commit(":1.1", token, 1, "\n", send));
    assert(gate.cancel(":1.1", token));
    assert(!gate.commit(":1.1", token, 2, "字", send));
    assert(!gate.begin(":1.1", token, until));
    assert(delivered == 2);
    Gate uncertain(root);
    assert(uncertain.begin(":1.1", token, until));
    auto fails = [](const std::string &) -> bool { throw std::runtime_error("private"); };
    assert(!uncertain.commit(":1.1", token, 0, "密", fails));
    assert(!uncertain.commit(":1.1", token, 0, "密", send));
    Gate gone(root);
    assert(gone.begin(":1.1", token, until));
    assert(unlink(file.c_str()) == 0);
    assert(!gone.commit(":1.1", token, 0, "中", send));
    { std::ofstream out(file); out << token; }
    assert(chmod(file.c_str(), 0600) == 0);
    assert(!gone.commit(":1.1", token, 0, "中", send));
    assert(chmod(file.c_str(), 0644) == 0);
    assert(!capability_matches(root, token));
    assert(unlink(file.c_str()) == 0);
    assert(symlink("/etc/passwd", file.c_str()) == 0);
    assert(!capability_matches(root, token));
    assert(unlink(file.c_str()) == 0);
    assert(rmdir(root.c_str()) == 0);
}
