/**
 * Supabase 数据库类型定义
 * 根据数据库 Schema 自动生成
 */

export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export interface Database {
  public: {
    Tables: {
      knowledge_nodes: {
        Row: {
          id: string
          order_num: number
          type: 'concept' | 'mechanism' | 'disease' | 'symptom' | 'treatment' | 'exam'
          title: string
          subject: string | null
          chapter: string | null
          knowledge_path: string[] | null
          content: string | null
          key_points: string[] | null
          causal_links: Json
          related_nodes: string[] | null
          difficulty: number
          tags: string[] | null
          source: string
          book_id: string | null
          textbook: string | null
          edition: string | null
          node_source: string | null
          inferred: boolean
          source_span: Json | null
          version: string | null
          created_at: string
          updated_at: string
        }
        Insert: {
          id: string
          order_num?: number
          type: 'concept' | 'mechanism' | 'disease' | 'symptom' | 'treatment' | 'exam'
          title: string
          subject?: string | null
          chapter?: string | null
          knowledge_path?: string[] | null
          content?: string | null
          key_points?: string[] | null
          causal_links?: Json
          related_nodes?: string[] | null
          difficulty?: number
          tags?: string[] | null
          source?: string
          book_id?: string | null
          textbook?: string | null
          edition?: string | null
          node_source?: string | null
          inferred?: boolean
          source_span?: Json | null
          version?: string | null
          created_at?: string
          updated_at?: string
        }
        Update: {
          id?: string
          order_num?: number
          type?: 'concept' | 'mechanism' | 'disease' | 'symptom' | 'treatment' | 'exam'
          title?: string
          subject?: string | null
          chapter?: string | null
          knowledge_path?: string[] | null
          content?: string | null
          key_points?: string[] | null
          causal_links?: Json
          related_nodes?: string[] | null
          difficulty?: number
          tags?: string[] | null
          source?: string
          book_id?: string | null
          textbook?: string | null
          edition?: string | null
          node_source?: string | null
          inferred?: boolean
          source_span?: Json | null
          version?: string | null
          created_at?: string
          updated_at?: string
        }
      }
      exam_questions: {
        Row: {
          id: string
          type: 'single' | 'multiple'
          question: string
          options: string[]
          answer: number
          explanation: string | null
          related_nodes: string[] | null
          difficulty: number
          source: string
          created_at: string
          updated_at: string
        }
        Insert: {
          id: string
          type: 'single' | 'multiple'
          question: string
          options: string[]
          answer: number
          explanation?: string | null
          related_nodes?: string[] | null
          difficulty?: number
          source?: string
          created_at?: string
          updated_at?: string
        }
        Update: {
          id?: string
          type?: 'single' | 'multiple'
          question?: string
          options?: string[]
          answer?: number
          explanation?: string | null
          related_nodes?: string[] | null
          difficulty?: number
          source?: string
          created_at?: string
          updated_at?: string
        }
      }
      causal_chains: {
        Row: {
          id: string
          title: string
          steps: Json
          related_nodes: string[] | null
          difficulty: number
          source: string
          creator_user_id: string | null
          created_at: string
          updated_at: string
        }
        Insert: {
          id: string
          title: string
          steps: Json
          related_nodes?: string[] | null
          difficulty?: number
          source?: string
          creator_user_id?: string | null
          created_at?: string
          updated_at?: string
        }
        Update: {
          id?: string
          title?: string
          steps?: Json
          related_nodes?: string[] | null
          difficulty?: number
          source?: string
          creator_user_id?: string | null
          created_at?: string
          updated_at?: string
        }
      }
      cases: {
        Row: {
          id: string
          title: string
          chief_complaint: string
          stages: Json
          difficulty: number
          related_nodes: string[] | null
          source: string
          creator_user_id: string | null
          created_at: string
          updated_at: string
        }
        Insert: {
          id: string
          title: string
          chief_complaint: string
          stages: Json
          difficulty?: number
          related_nodes?: string[] | null
          source?: string
          creator_user_id?: string | null
          created_at?: string
          updated_at?: string
        }
        Update: {
          id?: string
          title?: string
          chief_complaint?: string
          stages?: Json
          difficulty?: number
          related_nodes?: string[] | null
          source?: string
          creator_user_id?: string | null
          created_at?: string
          updated_at?: string
        }
      }
      user_profiles: {
        Row: {
          id: string
          nickname: string | null
          avatar_url: string | null
          preferences: Json
          ai_config: Json
          created_at: string
          updated_at: string
        }
        Insert: {
          id: string
          nickname?: string | null
          avatar_url?: string | null
          preferences?: Json
          ai_config?: Json
          created_at?: string
          updated_at?: string
        }
        Update: {
          id?: string
          nickname?: string | null
          avatar_url?: string | null
          preferences?: Json
          ai_config?: Json
          created_at?: string
          updated_at?: string
        }
      }
      feynman_records: {
        Row: {
          id: string
          user_id: string
          node_id: string
          transcript: string
          ai_score: Json
          feedback: string | null
          created_at: string
        }
        Insert: {
          id?: string
          user_id: string
          node_id: string
          transcript: string
          ai_score: Json
          feedback?: string | null
          created_at?: string
        }
        Update: {
          id?: string
          user_id?: string
          node_id?: string
          transcript?: string
          ai_score?: Json
          feedback?: string | null
          created_at?: string
        }
      }
      dialogue_records: {
        Row: {
          id: string
          user_id: string
          node_id: string
          messages: Json
          mastery_detected: boolean
          created_at: string
        }
        Insert: {
          id?: string
          user_id: string
          node_id: string
          messages: Json
          mastery_detected?: boolean
          created_at?: string
        }
        Update: {
          id?: string
          user_id?: string
          node_id?: string
          messages?: Json
          mastery_detected?: boolean
          created_at?: string
        }
      }
      case_records: {
        Row: {
          id: string
          user_id: string
          case_id: string
          current_stage: number
          stage_scores: Json
          total_score: number | null
          created_at: string
          updated_at: string
        }
        Insert: {
          id?: string
          user_id: string
          case_id: string
          current_stage?: number
          stage_scores?: Json
          total_score?: number | null
          created_at?: string
          updated_at?: string
        }
        Update: {
          id?: string
          user_id?: string
          case_id?: string
          current_stage?: number
          stage_scores?: Json
          total_score?: number | null
          created_at?: string
          updated_at?: string
        }
      }
      exam_records: {
        Row: {
          id: string
          user_id: string
          session_id: string
          question_id: string
          user_answer: number
          is_correct: boolean
          created_at: string
        }
        Insert: {
          id?: string
          user_id: string
          session_id: string
          question_id: string
          user_answer: number
          is_correct: boolean
          created_at?: string
        }
        Update: {
          id?: string
          user_id?: string
          session_id?: string
          question_id?: string
          user_answer?: number
          is_correct?: boolean
          created_at?: string
        }
      }
      exam_sessions: {
        Row: {
          id: string
          user_id: string
          question_ids: string[]
          score: number
          weak_nodes: string[] | null
          duration: number
          created_at: string
          updated_at: string
        }
        Insert: {
          id?: string
          user_id: string
          question_ids: string[]
          score?: number
          weak_nodes?: string[] | null
          duration?: number
          created_at?: string
          updated_at?: string
        }
        Update: {
          id?: string
          user_id?: string
          question_ids?: string[]
          score?: number
          weak_nodes?: string[] | null
          duration?: number
          created_at?: string
          updated_at?: string
        }
      }
      wrong_questions: {
        Row: {
          id: string
          user_id: string
          question_id: string
          node_id: string | null
          session_id: string | null
          retry_correct: boolean
          created_at: string
          updated_at: string
        }
        Insert: {
          id?: string
          user_id: string
          question_id: string
          node_id?: string | null
          session_id?: string | null
          retry_correct?: boolean
          created_at?: string
          updated_at?: string
        }
        Update: {
          id?: string
          user_id?: string
          question_id?: string
          node_id?: string | null
          session_id?: string | null
          retry_correct?: boolean
          created_at?: string
          updated_at?: string
        }
      }
      spaced_repetition: {
        Row: {
          id: string
          user_id: string
          node_id: string
          next_review: string
          interval: number
          ease_factor: number
          repetitions: number
          last_quality: number | null
          created_at: string
          updated_at: string
        }
        Insert: {
          id?: string
          user_id: string
          node_id: string
          next_review: string
          interval?: number
          ease_factor?: number
          repetitions?: number
          last_quality?: number | null
          created_at?: string
          updated_at?: string
        }
        Update: {
          id?: string
          user_id?: string
          node_id?: string
          next_review?: string
          interval?: number
          ease_factor?: number
          repetitions?: number
          last_quality?: number | null
          created_at?: string
          updated_at?: string
        }
      }
      study_activities: {
        Row: {
          id: string
          user_id: string
          type: 'feynman' | 'exam' | 'pathway' | 'case' | 'dialogue' | 'compare'
          node_id: string | null
          session_id: string | null
          record_id: string | null
          score: number | null
          duration: number
          metadata: Json
          created_at: string
        }
        Insert: {
          id?: string
          user_id: string
          type: 'feynman' | 'exam' | 'pathway' | 'case' | 'dialogue' | 'compare'
          node_id?: string | null
          session_id?: string | null
          record_id?: string | null
          score?: number | null
          duration?: number
          metadata?: Json
          created_at?: string
        }
        Update: {
          id?: string
          user_id?: string
          type?: 'feynman' | 'exam' | 'pathway' | 'case' | 'dialogue' | 'compare'
          node_id?: string | null
          session_id?: string | null
          record_id?: string | null
          score?: number | null
          duration?: number
          metadata?: Json
          created_at?: string
        }
      }
      favorites: {
        Row: {
          id: string
          user_id: string
          node_id: string
          created_at: string
        }
        Insert: {
          id?: string
          user_id: string
          node_id: string
          created_at?: string
        }
        Update: {
          id?: string
          user_id?: string
          node_id?: string
          created_at?: string
        }
      }
      learning_paths: {
        Row: {
          id: string
          user_id: string
          title: string
          node_ids: string[]
          progress: number
          created_at: string
          updated_at: string
        }
        Insert: {
          id?: string
          user_id: string
          title: string
          node_ids?: string[]
          progress?: number
          created_at?: string
          updated_at?: string
        }
        Update: {
          id?: string
          user_id?: string
          title?: string
          node_ids?: string[]
          progress?: number
          created_at?: string
          updated_at?: string
        }
      }
      study_plans: {
        Row: {
          id: string
          user_id: string
          goals: Json
          schedule: Json
          created_at: string
          updated_at: string
        }
        Insert: {
          id?: string
          user_id: string
          goals?: Json
          schedule?: Json
          created_at?: string
          updated_at?: string
        }
        Update: {
          id?: string
          user_id?: string
          goals?: Json
          schedule?: Json
          created_at?: string
          updated_at?: string
        }
      }
      study_goals: {
        Row: {
          id: string
          user_id: string
          type: string
          target: number
          current: number
          period: 'daily' | 'weekly' | 'monthly'
          created_at: string
          updated_at: string
        }
        Insert: {
          id?: string
          user_id: string
          type: string
          target: number
          current?: number
          period: 'daily' | 'weekly' | 'monthly'
          created_at?: string
          updated_at?: string
        }
        Update: {
          id?: string
          user_id?: string
          type?: string
          target?: number
          current?: number
          period?: 'daily' | 'weekly' | 'monthly'
          created_at?: string
          updated_at?: string
        }
      }
    }
    Views: {
      user_learning_stats: {
        Row: {
          user_id: string
          feynman_count: number
          exam_count: number
          pathway_count: number
          case_count: number
          total_duration: number
          study_days: number
        }
      }
      node_mastery: {
        Row: {
          user_id: string
          node_id: string
          node_title: string
          subject: string | null
          avg_accuracy: number
          avg_completeness: number
          avg_clarity: number
          avg_depth: number
          attempt_count: number
          last_attempt: string
        }
      }
    }
    Functions: {}
    Enums: {}
  }
}

// 导出常用类型别名
export type KnowledgeNode = Database['public']['Tables']['knowledge_nodes']['Row']
export type ExamQuestion = Database['public']['Tables']['exam_questions']['Row']
export type CausalChain = Database['public']['Tables']['causal_chains']['Row']
export type MedicalCase = Database['public']['Tables']['cases']['Row']
export type UserProfile = Database['public']['Tables']['user_profiles']['Row']
export type FeynmanRecord = Database['public']['Tables']['feynman_records']['Row']
export type DialogueRecord = Database['public']['Tables']['dialogue_records']['Row']
export type CaseRecord = Database['public']['Tables']['case_records']['Row']
export type ExamRecord = Database['public']['Tables']['exam_records']['Row']
export type ExamSession = Database['public']['Tables']['exam_sessions']['Row']
export type WrongQuestion = Database['public']['Tables']['wrong_questions']['Row']
export type SpacedRepetition = Database['public']['Tables']['spaced_repetition']['Row']
export type StudyActivity = Database['public']['Tables']['study_activities']['Row']
export type Favorite = Database['public']['Tables']['favorites']['Row']
export type LearningPath = Database['public']['Tables']['learning_paths']['Row']
export type StudyPlan = Database['public']['Tables']['study_plans']['Row']
export type StudyGoal = Database['public']['Tables']['study_goals']['Row']

// AI 评分类型
export interface AIScore {
  accuracy: number
  completeness: number
  clarity: number
  depth: number
}

// 统计视图类型
export type UserLearningStats = Database['public']['Views']['user_learning_stats']['Row']
export type NodeMastery = Database['public']['Views']['node_mastery']['Row']