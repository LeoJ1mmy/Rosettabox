#!/usr/bin/env python3
"""
添加缺失的技術術語到詞彙表
"""
import sys
sys.path.insert(0, '/home/leonv02/work/LeoQxAIBox/voice-text-processor/backend')

from vocabulary.vocabulary_config import vocabulary_config

# 添加缺失的術語
missing_terms = [
    {
        "term": "OpenAI",
        "corrections": ["open ai", "ope。ai", "openai", "open a.i.", "open AI"],
        "context": ["gpt", "chatgpt", "whisper", "ai", "api"],
        "priority": 10,
        "case_sensitive": False
    },
    {
        "term": "Gemini",
        "corrections": ["gemi。i", "gemini", "gem i ni", "geminai"],
        "context": ["google", "ai", "model", "llm"],
        "priority": 9,
        "case_sensitive": False
    },
    {
        "term": "mini",
        "corrections": ["mi。i", "mm", "mini", "miny"],
        "context": ["model", "gpt", "version", "4.1"],
        "priority": 8,
        "case_sensitive": False
    },
    {
        "term": "token",
        "corrections": ["toke。", "token", "tokens", "tok en"],
        "context": ["api", "limit", "count", "usage"],
        "priority": 9,
        "case_sensitive": False
    },
    {
        "term": "agent",
        "corrections": ["age。t", "agent", "agents", "ajent"],
        "context": ["ai", "autonomous", "intelligent", "system"],
        "priority": 9,
        "case_sensitive": False
    },
    {
        "term": "document",
        "corrections": ["docume。", "document", "doc", "documents"],
        "context": ["file", "text", "content", "upload"],
        "priority": 7,
        "case_sensitive": False
    },
    {
        "term": "HTML",
        "corrections": ["hdmi", "HTML", "H T M L", "h.t.m.l."],
        "context": ["web", "page", "website", "markup"],
        "priority": 9,
        "case_sensitive": True
    },
    {
        "term": "prompt",
        "corrections": ["pump", "prompt", "prompts", "prom pt"],
        "context": ["ai", "instruction", "system", "template"],
        "priority": 9,
        "case_sensitive": False
    },
    {
        "term": "CSV",
        "corrections": ["C S V", "c.s.v.", "csv", "CSV"],
        "context": ["file", "data", "excel", "spreadsheet"],
        "priority": 8,
        "case_sensitive": True
    },
    {
        "term": "temperature",
        "corrections": ["temperature", "temp", "temprature"],
        "context": ["ai", "parameter", "model", "setting"],
        "priority": 7,
        "case_sensitive": False
    },
    {
        "term": "web search",
        "corrections": ["web search", "websearch", "web searching"],
        "context": ["google", "internet", "online", "search"],
        "priority": 7,
        "case_sensitive": False
    },
    {
        "term": "file",
        "corrections": ["file", "files", "fyl"],
        "context": ["upload", "download", "document", "data"],
        "priority": 6,
        "case_sensitive": False
    },
    {
        "term": "model",
        "corrections": ["model", "models", "modle"],
        "context": ["ai", "llm", "gpt", "training"],
        "priority": 8,
        "case_sensitive": False
    },
    {
        "term": "demo",
        "corrections": ["demo", "demos", "demonstration"],
        "context": ["test", "example", "sample", "trial"],
        "priority": 6,
        "case_sensitive": False
    },
]

print("🚀 開始添加缺失的技術術語...")
print(f"準備添加 {len(missing_terms)} 個術語\n")

added = 0
updated = 0
skipped = 0

for term_data in missing_terms:
    term = term_data["term"]

    # 檢查是否已存在
    existing = vocabulary_config.get_term(term)

    if existing:
        print(f"⚠️  術語已存在: {term} - 更新中...")
        success = vocabulary_config.update_term(
            term,
            corrections=term_data["corrections"],
            context=term_data["context"],
            priority=term_data["priority"],
            case_sensitive=term_data["case_sensitive"]
        )
        if success:
            updated += 1
            print(f"   ✅ 已更新: {term}")
        else:
            print(f"   ❌ 更新失敗: {term}")
    else:
        print(f"➕ 添加新術語: {term}")
        success = vocabulary_config.add_term(
            term=term,
            corrections=term_data["corrections"],
            context=term_data["context"],
            priority=term_data["priority"],
            case_sensitive=term_data["case_sensitive"]
        )
        if success:
            added += 1
            print(f"   ✅ 已添加: {term}")
        else:
            print(f"   ❌ 添加失敗: {term}")

print("\n" + "="*60)
print("📊 總結:")
print(f"   ✅ 新增: {added} 個")
print(f"   🔄 更新: {updated} 個")
print(f"   ⏭️  跳過: {skipped} 個")
print(f"   📚 詞彙表總數: {len(vocabulary_config.get_all_terms())} 個術語")
print("="*60)

print("\n🎉 術語添加完成！")
print("\n💡 提示: 重啟後端服務後，這些術語將自動用於 initial_prompt 生成")
