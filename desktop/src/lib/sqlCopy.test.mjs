import assert from "node:assert/strict";
import test from "node:test";
import {
  buildInsertSql,
  buildRowJson,
  formatSqlValue,
  normalizeCopyValue,
  quoteIdentifier,
} from "../../dist-tests/sqlCopy.js";

test("quoteIdentifier escapes backticks", () => {
  assert.equal(quoteIdentifier("user`name"), "`user``name`");
});

test("formatSqlValue handles NULL, strings, numbers, booleans and objects", () => {
  assert.equal(formatSqlValue(null), "NULL");
  assert.equal(formatSqlValue("O'Reilly"), "'O''Reilly'");
  assert.equal(formatSqlValue("C:\\tmp"), "'C:\\\\tmp'");
  assert.equal(formatSqlValue(123), "123");
  assert.equal(formatSqlValue(true), "1");
  assert.equal(formatSqlValue(false), "0");
  assert.equal(formatSqlValue({ role: "admin" }), "'{\"role\":\"admin\"}'");
});

test("buildRowJson preserves requested column order", () => {
  const json = buildRowJson(["id", "name", "missing"], { name: "Ada", id: 1 });
  assert.equal(json, '{\n  "id": 1,\n  "name": "Ada",\n  "missing": null\n}');
});

test("buildInsertSql generates MySQL-compatible INSERT", () => {
  const sql = buildInsertSql(
    "platform_accounts",
    ["id", "nickname", "active", "payload", "deleted_at"],
    {
      id: 1,
      nickname: "O'Reilly",
      active: true,
      payload: { channel: "xhs" },
      deleted_at: null,
    },
    "creatorhub",
  );

  assert.equal(
    sql,
    "INSERT INTO `creatorhub`.`platform_accounts` (`id`, `nickname`, `active`, `payload`, `deleted_at`)\n" +
      "VALUES (1, 'O''Reilly', 1, '{\"channel\":\"xhs\"}', NULL);",
  );
});

test("normalizeCopyValue returns full raw copy text", () => {
  assert.equal(normalizeCopyValue(null), "NULL");
  assert.equal(normalizeCopyValue({ a: 1 }), "{\"a\":1}");
});
