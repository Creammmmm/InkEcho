from pathlib import Path
import shutil,os,ast,hashlib
b=Path('/home/lth/github/InkEcho/dist');r=b/'gnome-bounded-owned-r3-20261030';r.mkdir();source=b/'gnome46-bounded-owned-desktop-20261030/input/candidate-src';out=r/'candidate-src';shutil.copytree(source,out,copy_function=os.link)
def replace(p,s):
 q=p.with_name(p.name+'.new');q.write_text(s);q.replace(p)
p=out/'inkecho/platform/ibus_owned_candidate/extension.js';s=p.read_text();s=s.replace('[this._gate.begin(invocation.get_sender(), [name, token])]', '[false]');s=s.replace('''        const result = await this._gate.commit(invocation.get_sender(), sequence, text);
        invocation.return_value(new GLib.Variant('(s)', [result]));''','''        invocation.return_value(new GLib.Variant('(s)', ['rejected']));''');s=s.replace('[this._gate.beginBatch(invocation.get_sender(), [name, token], version)]','[false]');s=s.replace('''        const result = await this._gate.commit(invocation.get_sender(), sequence, text, true);
        invocation.return_value(new GLib.Variant('(s)', [result]));''','''        invocation.return_value(new GLib.Variant('(s)', ['rejected']));''');s=s.replace('    BeginAsync([name, token], invocation) {','    // Legacy methods stay introspectable but can never create or mutate a task.\n    // A matching upgraded client must negotiate the bounded methods.\n    BeginAsync([name, token], invocation) {');replace(p,s)
p=out/'inkecho/platform/ibus_owned.py';s=p.read_text();needle='''        if not (
            exact("BeginBounded", "ssut", "b")''';idx=s.index(needle);end=s.index('\n    async def begin(self):',idx);s=s[:idx]+'''        bounded_advertised = any(
            method.get("name") in {"BeginBounded", "CommitBounded"}
            for method in methods
        )
        if bounded_advertised:
            if not (
                exact("BeginBounded", "ssut", "b")
                and exact("CommitBounded", "ust", "s")
                and exact("Cancel", "", "b")
            ):
                raise CandidateError("unavailable")
            return True
        complete_legacy = exact("Cancel", "", "b") and (
            (exact("BeginBatch", "ssu", "b") and exact("CommitBatch", "us", "s"))
            or (exact("Begin", "ss", "b") and exact("Commit", "us", "s"))
        )
        if complete_legacy:
            raise CandidateError("upgrade_required")
        raise CandidateError("unavailable")
''' +s[end:]
s=s.replace('''                "untrusted_owner",
            }:''','''                "untrusted_owner",
                "upgrade_required",
            }:''');replace(p,s)
p=out/'inkecho/platform/ibus_owned_default.py';s=p.read_text().replace('''            "authorization_failed",
            "permission_denied",''','''            "authorization_failed",
            "upgrade_required",
            "permission_denied",''');replace(p,s)
p=out/'inkecho/platform/output_router.py';s=p.read_text().replace('''                    "authorization_failed",
                    "composition_guard_unavailable",''','''                    "authorization_failed",
                    "upgrade_required",
                    "composition_guard_unavailable",''');replace(p,s)
p=out/'inkecho/logging.py';s=p.read_text().replace('''        "ibus_unavailable",''','''        "ibus_unavailable",
        "ibus_upgrade_required",''');replace(p,s)
p=out/'inkecho/app.py';s=p.read_text();needle='''    "ibus_authorization_failed":''';idx=s.index(needle);s=s[:idx]+'''    "ibus_upgrade_required": (
        "IBus 扩展仍在运行旧协议。请停用并卸载旧扩展，安装匹配版本后重新登录桌面加载；"
        "本次未自动重试。"
    ),
''' +s[idx:];replace(p,s)
p=out/'inkecho/ui/information.py';s=p.read_text();needle='''                "再安装并启用新版；安装不会自动覆盖旧扩展。"''';assert needle in s;s=s.replace(needle,needle+'''\n                "升级后需重新登录桌面加载新协议；只停用再启用可能仍使用缓存代码。"
                "新版扩展拒绝旧协议，旧应用可能显示授权失败；请更新并重启 InkEcho。"''');replace(p,s)
p=out/'inkecho/platform/owned_installation.py';s=p.read_text();m=ast.parse(s);n=next(n for n in m.body if isinstance(n,ast.Assign)and any(isinstance(x,ast.Name)and x.id=='FILES'for x in n.targets));rows=ast.literal_eval(n.value)
for name,item in rows.items():raw=(out/'inkecho/platform/ibus_owned_candidate'/name).read_bytes();item.update(sha256=hashlib.sha256(raw).hexdigest(),size=len(raw))
lines=s.splitlines(keepends=True);replace(p,''.join(lines[:n.lineno-1])+'FILES = '+repr(rows)+'\n'+''.join(lines[n.end_lineno:]));print(r)
