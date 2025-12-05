-- 如果 paper 表中的 alias 字段和 full_name 字段一样，就清空 alias
UPDATE paper 
SET alias = NULL 
WHERE alias = full_name 
  AND alias IS NOT NULL 
  AND full_name IS NOT NULL;

-- 查看更新前的统计
-- SELECT COUNT(*) as count_before FROM paper WHERE alias = full_name AND alias IS NOT NULL;

-- 查看更新后的统计
-- SELECT COUNT(*) as count_after FROM paper WHERE alias = full_name AND alias IS NOT NULL;


