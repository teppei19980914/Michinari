import { apiClient } from './client'
import type { components } from '../types/api.d.ts'

export type ExamTemplateSubject = components['schemas']['ExamTemplateSubject']
export type ExamTemplateMaterial = components['schemas']['ExamTemplateMaterial']
export type ExamTemplateRead = components['schemas']['ExamTemplateRead']

/** 資格試験テンプレート一覧（仕様書「資格モードのテンプレート」）。 */
export function listExamTemplates(): Promise<ExamTemplateRead[]> {
  return apiClient.get<ExamTemplateRead[]>('/exam-templates')
}
