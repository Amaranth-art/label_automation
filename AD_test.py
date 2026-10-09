import ldap3

AD_SERVER = 'ldap://CNDGNDCS02.delta.corp'
DOMAIN = 'delta'

username = input('AD用户名（工号，如 shuhanli.lee）: ')
password = input('AD密码: ')

server = ldap3.Server(AD_SERVER, get_info=ldap3.ALL)

# 格式1：delta\shuhanli.lee
conn = ldap3.Connection(
    server,
    user=f'{DOMAIN}\\{username}',
    password=password,
    authentication=ldap3.NTLM
)

if conn.bind():
    print('✅ AD 认证成功')
    print('身份:', conn.extend.standard.who_am_i())
else:
    print('❌ 格式1失败:', conn.result)

    # 格式2：shuhanli.lee@delta.corp
    conn2 = ldap3.Connection(
        server,
        user=f'{username}@delta.corp',
        password=password,
        authentication=ldap3.NTLM
    )
    if conn2.bind():
        print('✅ 格式2成功')
        print('身份:', conn2.extend.standard.who_am_i())
    else:
        print('❌ 格式2也失败:', conn2.result)