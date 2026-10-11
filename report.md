# 迅睿CMS模板引擎{code}标签存在代码执行绕过漏洞

## 漏洞基本信息



| 漏洞厂商 | 迅睿CMS (XunRuiCMS)       |
| -------- | ------------------------- |
| 厂商官网 | https://www.xunruicms.com |

## POC

模板标签 `{code}...{/code}` 绕过模板编译器，其中的原始PHP代码被原样保留并通过 `require` 执行。View.php:724-744 的 `_code` 方法通过正则 `{code}(.*?){/code}` 提取内容并替换为占位符，编译完成后将占位符还原为原始PHP代码。Docker验证: 10/10次成功，payload `<?php echo 'CODE_BYPASS_OK'; ?>` 成功输出标记字符串。

## 触发过程

1. 获取后台管理权限并登录
2. 上传 `.html` 文件，内容包含:
```
{code}
<?php system('id'); ?>
{/code}
```
3. 将文件移动到模板目录

4. 当模板被加载时，`{code}` 标签内的PHP代码被提取保存，编译完成后还原

5. 还原的PHP代码通过 `require` 执行，实现代码执行

   ![image-20260509132303326](../../../../AppData/Roaming/Typora/typora-user-images/image-20260509132303326.png)

## 漏洞URL

- 项目官网: https://www.xunruicms.com
- CWE-94参考: https://cwe.mitre.org/data/definitions/94.html
- CNVD参考: https://www.cnvd.org.cn

## 漏洞描述

【漏洞概述】迅睿CMS模板引擎的 `{code}` 标签设计上用于在模板中嵌入PHP代码。View.php第724-744行的编译流程为：提取 `{code}...{/code}` 内容 → 替换为占位符 → 执行常规编译 → 还原原始代码。这种设计导致完全绕过了模板编译器的安全转换，原始PHP代码被原样嵌入最终执行的PHP文件中。

【受影响代码】文件: `dayrui/Fcms/Core/View.php` 第724-744行:
```php
// _code() 方法提取并还原 {code}...{/code} 中的原始PHP代码
preg_match_all('/{code}(.*?){\/code}/is', $content, $matches);
// 替换为占位符 → 执行其他编译 → 还原原始代码
```

【与其他标签的区别】`{php}` 和 `{func()}` 标签通过正则替换生成PHP代码，而 `{code}` 标签实现的是编译器的完全绕过——其中的内容不被任何正则匹配或转换，以原始形态被执行。三种标签共同构成了SSTI攻击面。

## 临时解决方案

1. 删除或注释 View.php 中 `_code()` 方法的调用
2. 在 `{code}` 标签处理中增加内容过滤，移除 `<?php` 标签
3. 限制 `{code}` 标签仅包含HTML代码而非PHP代码

## 正式解决方案

1. 完全移除 `{code}` 标签支持，此为模板引擎提供的原始PHP执行通道
2. 如必须保留，应在编译后对还原内容进行安全扫描
3. 联系厂商获取官方补丁
