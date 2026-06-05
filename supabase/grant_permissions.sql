GRANT SELECT ON knowledge_nodes TO anon, authenticated, service_role;
GRANT SELECT ON exam_questions TO anon, authenticated, service_role;
GRANT SELECT ON causal_chains TO anon, authenticated, service_role;
GRANT SELECT ON cases TO anon, authenticated, service_role;

GRANT ALL ON user_profiles TO authenticated, service_role;
GRANT ALL ON feynman_records TO authenticated, service_role;
GRANT ALL ON dialogue_records TO authenticated, service_role;
GRANT ALL ON case_records TO authenticated, service_role;
GRANT ALL ON exam_records TO authenticated, service_role;
GRANT ALL ON exam_sessions TO authenticated, service_role;
GRANT ALL ON wrong_questions TO authenticated, service_role;
GRANT ALL ON spaced_repetition TO authenticated, service_role;
GRANT ALL ON study_activities TO authenticated, service_role;
GRANT ALL ON favorites TO authenticated, service_role;
GRANT ALL ON learning_paths TO authenticated, service_role;
GRANT ALL ON study_plans TO authenticated, service_role;
GRANT ALL ON study_goals TO authenticated, service_role;

GRANT SELECT ON user_learning_stats TO anon, authenticated, service_role;
GRANT SELECT ON node_mastery TO anon, authenticated, service_role;
