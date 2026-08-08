# 13_MCP_TOOL_CATALOG — 百宝箱工具目录

> **锁定状态：FROZEN（D2 冻结）**
> 本文件定义所有供百宝箱调用的工具及其输入输出 Schema。
> 工具名、参数名、类型、required 字段不得随意修改。
> 百宝箱工具配置必须与本文件严格一致。

---

## 0. 通用约定

### 0.1 工具统一响应格式

所有工具返回以下 JSON 结构（与 `04_API_CONTRACTS.md §9.3` 相同）：

```json
{
  "code": "int",
  "message": "string",
  "request_id": "string — UUID",
  "data": "object | null",
  "error": "object | null — {type: string, detail: string}"
}
```

### 0.2 错误码（与 04_API_CONTRACTS.md §9.4 一致）

| code | 含义 |
|------|------|
| 0 | 成功 |
| -1 | 通用错误 |
| -2 | 参数校验失败 |
| -3 | 资源不存在 |
| -4 | LLM 调用失败（返回 fallback 数据） |
| -5 | 数据库错误 |
| -6 | 超时 |

### 0.3 调用方式

```
方式A (MCP):  百宝箱 MCP Client → CareerPulse MCP Server
方式B (HTTP): 百宝箱 HTTP 工具 → POST https://<host>/api/tbox/<tool_name>
              Headers: Authorization: Bearer <TOKEN>
              Content-Type: application/json
              Timeout: 30s
```

### 0.4 隐私约束

- 所有 `input_summary` / `output_summary` 及日志中**禁止**出现手机号、邮箱、身份证号、完整简历文本
- 号码脱敏：`138****1234`
- 邮箱脱敏：`u***@example.com`

---

## 1. analyze_student_profile

**功能**：解析用户简历或表单，生成结构化学生能力画像

**调用时机**：用户输入个人情况后，百宝箱首次调用

### 1.1 输入

```json
{
  "type": "object",
  "properties": {
    "session_id": {
      "type": "string",
      "description": "会话ID, e.g. sess-20260804-001"
    },
    "resume_text": {
      "type": "string",
      "description": "简历文本内容（可选, 与 form_fields 至少提供一个）"
    },
    "form_fields": {
      "type": "object",
      "description": "手动填写的表单字段（可选）",
      "properties": {
        "name": {"type": "string"},
        "education_level": {"type": "string", "enum": ["专科", "本科", "硕士", "博士"]},
        "major": {"type": "string"},
        "graduation_year": {"type": "integer"},
        "skills": {"type": "string"},
        "certificates": {"type": "string"},
        "internships": {"type": "string"},
        "projects": {"type": "string"},
        "self_evaluation": {"type": "string"},
        "target_job": {"type": "string"},
        "target_industry": {"type": "string"}
      }
    }
  },
  "required": ["session_id"]
}
```

### 1.2 输出

```json
{
  "type": "object",
  "properties": {
    "student_id": {"type": "integer"},
    "name": {"type": "string"},
    "basic_info": {
      "type": "object",
      "properties": {
        "education_level": {"type": "string"},
        "major": {"type": "string"},
        "graduation_year": {"type": "integer"},
        "target_job": {"type": "string"},
        "target_industry": {"type": "string"},
        "years_of_experience": {"type": "number"}
      }
    },
    "abilities": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "tag": {"type": "string"},
          "level": {"type": "integer", "minimum": 1, "maximum": 5},
          "confidence": {"type": "number", "minimum": 0, "maximum": 1},
          "evidence": {"type": "string"}
        },
        "required": ["tag", "level", "confidence", "evidence"]
      }
    },
    "competitiveness_score": {"type": "number", "minimum": 0, "maximum": 100},
    "completeness": {"type": "number", "minimum": 0, "maximum": 1},
    "missing_fields": {
      "type": "array",
      "items": {"type": "string"}
    }
  }
}
```

### 1.3 百宝箱对话指引

- `completeness < 0.5` → 提示信息不完整，追问 `missing_fields`
- `confidence < 0.3` 的 ability → 追问确认
- 画像完成后 → 建议下一步 "分析目标岗位"

---

## 2. analyze_job_and_trend

**功能**：分析目标岗位的能力要求和职业趋势

**调用时机**：学生画像完成后，用户确认目标岗位

### 2.1 输入

```json
{
  "type": "object",
  "properties": {
    "session_id": {"type": "string"},
    "job_id": {
      "type": "integer",
      "description": "岗位ID（可选, 与 job_title 至少提供一个）"
    },
    "job_title": {
      "type": "string",
      "description": "岗位名称（可选, 与 job_id 至少提供一个）"
    },
    "industry": {
      "type": "string",
      "description": "行业（可选, 用于趋势分析）"
    }
  },
  "required": ["session_id"]
}
```

### 2.2 输出

```json
{
  "type": "object",
  "properties": {
    "job_profile": {
      "type": "object",
      "properties": {
        "job_id": {"type": "integer"},
        "title": {"type": "string"},
        "normalized_title": {"type": "string"},
        "industry": {"type": "string"},
        "required_abilities": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "tag": {"type": "string"},
              "required_level": {"type": "integer", "minimum": 1, "maximum": 5},
              "weight": {"type": "number", "minimum": 0, "maximum": 1},
              "importance": {"type": "string", "enum": ["critical", "important", "nice_to_have"]}
            },
            "required": ["tag", "required_level", "weight", "importance"]
          }
        },
        "soft_skills": {"type": "array", "items": {"type": "string"}},
        "salary_range": {"type": "string"},
        "job_description": {"type": "string"}
      }
    },
    "trend_result": {
      "type": "object",
      "properties": {
        "job_title": {"type": "string"},
        "industry": {"type": "string"},
        "trend_summary": {"type": "string"},
        "hot_skills": {"type": "array", "items": {"type": "string"}},
        "rising_skills": {"type": "array", "items": {"type": "string"}},
        "declining_skills": {"type": "array", "items": {"type": "string"}},
        "ai_risk_assessment": {"type": "string", "enum": ["low", "medium", "high"]},
        "ai_risk_detail": {"type": "string"},
        "development_opportunities": {"type": "array", "items": {"type": "string"}},
        "development_risks": {"type": "array", "items": {"type": "string"}},
        "data_source": {"type": "string"}
      }
    }
  }
}
```

### 2.3 百宝箱对话指引

- 展示 `required_abilities` 后 → 建议 "下一步计算匹配度"
- `trend_result.ai_risk_assessment = "high"` → 提示用户关注替代风险
- `trend_result` 数据应引用知识库来源

---

## 3. calculate_job_match

**功能**：计算人岗匹配度、能力缺口和提升优先级

**调用时机**：学生画像 + 岗位画像都完成后

### 3.1 输入

```json
{
  "type": "object",
  "properties": {
    "session_id": {"type": "string"},
    "student_id": {"type": "integer"},
    "job_id": {"type": "integer"}
  },
  "required": ["session_id", "student_id", "job_id"]
}
```

### 3.2 输出

```json
{
  "type": "object",
  "properties": {
    "overall_score": {"type": "number", "minimum": 0, "maximum": 100},
    "dimensions": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": {"type": "string"},
          "student_score": {"type": "number"},
          "job_required": {"type": "number"},
          "gap": {"type": "number"},
          "weight": {"type": "number"}
        },
        "required": ["name", "student_score", "job_required", "gap", "weight"]
      }
    },
    "ability_gaps": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "tag": {"type": "string"},
          "current_level": {"type": "integer"},
          "required_level": {"type": "integer"},
          "gap": {"type": "integer", "minimum": 0},
          "priority": {"type": "integer", "minimum": 1}
        },
        "required": ["tag", "current_level", "required_level", "gap", "priority"]
      }
    },
    "gap_analysis": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "item": {"type": "string"},
          "status": {"type": "string", "enum": ["missing", "insufficient", "adequate"]},
          "suggestion": {"type": "string"}
        },
        "required": ["item", "status", "suggestion"]
      }
    },
    "strengths": {"type": "array", "items": {"type": "string"}},
    "matching_algorithm_version": {"type": "string", "const": "deterministic-v1"}
  }
}
```

### 3.3 百宝箱对话指引

- `overall_score < 40` → 坦诚告知差距，建议调整目标
- `overall_score >= 70` → 鼓励，展示匹配优势
- `ability_gaps` 按 `priority` 升序展示（priority=1 最先展示）
- 必须说明"匹配分由算法计算，非AI估计"

---

## 4. recommend_career_path

**功能**：推荐 3年/5年职业发展路径和学习计划

**调用时机**：匹配分析完成后

### 4.1 输入

```json
{
  "type": "object",
  "properties": {
    "session_id": {"type": "string"},
    "student_id": {"type": "integer"},
    "job_id": {"type": "integer"}
  },
  "required": ["session_id", "student_id", "job_id"]
}
```

### 4.2 输出

```json
{
  "type": "object",
  "properties": {
    "path_plan": {
      "type": "object",
      "properties": {
        "target_job": {"type": "string"},
        "plan_3year": {
          "type": "object",
          "properties": {
            "phases": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "phase": {"type": "integer"},
                  "duration_months": {"type": "integer"},
                  "target_role": {"type": "string"},
                  "required_abilities": {"type": "array", "items": {"type": "string"}},
                  "tasks": {"type": "array", "items": {"type": "string"}},
                  "milestone": {"type": "string"}
                },
                "required": ["phase", "duration_months", "target_role", "required_abilities", "tasks", "milestone"]
              }
            },
            "total_score": {"type": "number"}
          }
        },
        "plan_5year": {
          "type": "object",
          "properties": {
            "phases": {"type": "array"},
            "total_score": {"type": "number"}
          }
        },
        "alternative_paths": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "type": {"type": "string", "enum": ["vertical", "lateral"]},
              "target_role": {"type": "string"},
              "score": {"type": "number"},
              "reason": {"type": "string"}
            },
            "required": ["type", "target_role", "score", "reason"]
          }
        },
        "path_algorithm_version": {"type": "string", "const": "graph-search-v1"}
      }
    },
    "learning_plan": {
      "type": "object",
      "properties": {
        "phases": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "phase": {"type": "integer"},
              "title": {"type": "string"},
              "tasks": {
                "type": "array",
                "items": {
                  "type": "object",
                  "properties": {
                    "task_id": {"type": "string"},
                    "description": {"type": "string"},
                    "target_ability": {"type": "string"},
                    "estimated_hours": {"type": "integer"},
                    "resources": {"type": "array", "items": {"type": "string"}}
                  },
                  "required": ["task_id", "description", "target_ability", "estimated_hours"]
                }
              }
            },
            "required": ["phase", "title", "tasks"]
          }
        },
        "certificate_suggestions": {"type": "array", "items": {"type": "string"}},
        "project_suggestions": {"type": "array", "items": {"type": "string"}}
      }
    }
  }
}
```

### 4.3 百宝箱对话指引

- 展示路径时说明"路径评分由算法计算"
- 如有 alternative_paths → 提供"也可考虑转岗路线"
- 学习计划按 phase 逐阶段展示

---

## 5. generate_and_score_training

**功能**：生成职场训练题 / 对用户回答进行评分

**调用时机**：
- **生成模式**：路径规划后，用户希望开始训练 → 不传 `user_answer`
- **评分模式**：用户提交回答后 → 传 `user_answer`

### 5.1 输入

```json
{
  "type": "object",
  "properties": {
    "session_id": {"type": "string"},
    "student_id": {"type": "integer"},
    "job_id": {"type": "integer"},
    "training_type": {
      "type": "string",
      "enum": ["remote_collaboration", "ai_office_task", "cross_role_communication"],
      "description": "训练类型"
    },
    "training_id": {
      "type": "string",
      "description": "已有训练ID（评分模式时必须提供）"
    },
    "user_answer": {
      "type": "string",
      "description": "用户回答文本（评分模式时必须提供, 生成模式不传）"
    }
  },
  "required": ["session_id", "student_id", "job_id", "training_type"]
}
```

### 5.2 输出（生成模式）→ TrainingTask

```json
{
  "type": "object",
  "properties": {
    "mode": {"type": "string", "const": "generate"},
    "training_id": {"type": "string"},
    "type": {"type": "string", "enum": ["remote_collaboration", "ai_office_task", "cross_role_communication"]},
    "title": {"type": "string"},
    "scenario": {"type": "string"},
    "task_description": {"type": "string"},
    "evaluation_criteria": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "dimension": {"type": "string"},
          "max_score": {"type": "number"},
          "weight": {"type": "number"},
          "description": {"type": "string"}
        },
        "required": ["dimension", "max_score", "weight", "description"]
      }
    },
    "target_abilities": {"type": "array", "items": {"type": "string"}},
    "reference_answer": {"type": "string"}
  }
}
```

### 5.3 输出（评分模式）→ TrainingScore

```json
{
  "type": "object",
  "properties": {
    "mode": {"type": "string", "const": "score"},
    "training_id": {"type": "string"},
    "total_score": {"type": "number", "minimum": 0, "maximum": 100},
    "dimension_scores": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "dimension": {"type": "string"},
          "score": {"type": "number"},
          "comment": {"type": "string"}
        },
        "required": ["dimension", "score", "comment"]
      }
    },
    "overall_comment": {"type": "string"},
    "improvement_suggestions": {"type": "array", "items": {"type": "string"}},
    "ability_updates": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "tag": {"type": "string"},
          "level_change": {"type": "integer", "minimum": -1, "maximum": 1}
        },
        "required": ["tag", "level_change"]
      }
    }
  }
}
```

### 5.4 百宝箱对话指引

- 生成模式 → 展示题目，邀请用户作答
- 评分模式 → 展示评分结果，标注 `ability_updates`
- 训练完成后 → 建议"查看推荐资源"或"再来一题"

---

## 6. recommend_learning_and_job_resources

**功能**：推荐学习资源和岗位资源

**调用时机**：匹配分析或训练评分后

### 6.1 输入

```json
{
  "type": "object",
  "properties": {
    "session_id": {"type": "string"},
    "ability_gaps": {
      "type": "array",
      "items": {"type": "string"},
      "description": "需要提升的能力标签列表"
    },
    "target_job": {"type": "string"}
  },
  "required": ["session_id"]
}
```

### 6.2 输出

```json
{
  "type": "object",
  "properties": {
    "learning_resources": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "title": {"type": "string"},
          "type": {"type": "string", "enum": ["course", "book", "practice", "certificate"]},
          "url": {"type": "string"},
          "target_ability": {"type": "string"},
          "description": {"type": "string"}
        },
        "required": ["title", "type", "target_ability"]
      }
    },
    "job_resources": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "title": {"type": "string"},
          "company": {"type": "string"},
          "match_score": {"type": "number"},
          "url": {"type": "string"}
        },
        "required": ["title", "company"]
      }
    },
    "certificate_suggestions": {
      "type": "array",
      "items": {"type": "string"}
    }
  }
}
```

---

## 7. save_growth_feedback

**功能**：保存用户反馈，更新成长档案和学习优先级

**调用时机**：用户完成一轮职业规划后

### 7.1 输入

```json
{
  "type": "object",
  "properties": {
    "session_id": {"type": "string"},
    "user_id": {"type": "string"},
    "satisfaction": {
      "type": "integer",
      "minimum": 1,
      "maximum": 5,
      "description": "总体满意度 1-5"
    },
    "path_rating": {
      "type": "integer",
      "minimum": 1,
      "maximum": 5,
      "description": "路径规划满意度 (可选)"
    },
    "training_rating": {
      "type": "integer",
      "minimum": 1,
      "maximum": 5,
      "description": "训练满意度 (可选)"
    },
    "resource_rating": {
      "type": "integer",
      "minimum": 1,
      "maximum": 5,
      "description": "资源推荐满意度 (可选)"
    },
    "comments": {
      "type": "string",
      "description": "文字反馈 (可选)"
    }
  },
  "required": ["session_id", "user_id", "satisfaction"]
}
```

### 7.2 输出

```json
{
  "type": "object",
  "properties": {
    "feedback_saved": {"type": "boolean"},
    "growth_archive_updated": {"type": "boolean"},
    "updated_priorities": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "tag": {"type": "string"},
          "old_priority": {"type": "integer"},
          "new_priority": {"type": "integer"},
          "reason": {"type": "string"}
        },
        "required": ["tag", "old_priority", "new_priority", "reason"]
      }
    },
    "growth_snapshot": {
      "type": "object",
      "properties": {
        "competitiveness_score": {"type": "number"},
        "completed_trainings": {"type": "integer"},
        "completed_phases": {"type": "integer"},
        "growth_trend": {"type": "string", "enum": ["improving", "stable", "declining"]}
      }
    }
  }
}
```

---

## 8. 工具清单总览

| # | 工具名 | 输入最小字段 | 输出核心字段 | 调用 LLM | 优先级 |
|---|--------|------------|------------|---------|--------|
| 1 | `analyze_student_profile` | session_id | student_profile | ✅ | P0 |
| 2 | `analyze_job_and_trend` | session_id | job_profile + trend_result | ✅ | P0 |
| 3 | `calculate_job_match` | session_id + student_id + job_id | match_result | ✅(仅解释) | P0 |
| 4 | `recommend_career_path` | session_id + student_id + job_id | path_plan + learning_plan | ✅(仅描述) | P1 |
| 5 | `generate_and_score_training` | session_id + student_id + job_id + training_type | TrainingTask / TrainingScore | ✅ | P1 |
| 6 | `recommend_learning_and_job_resources` | session_id | learning_resources + job_resources | ❌ | P1 |
| 7 | `save_growth_feedback` | session_id + user_id + satisfaction | feedback_result | ❌ | P1 |

---

## 9. 版本记录

| 日期 | 版本 | 变更 | 作者 |
|------|------|------|------|
| 2026-08-04 | v1.0 | 初始冻结：7个工具完整输入输出Schema | 技术负责人 |
