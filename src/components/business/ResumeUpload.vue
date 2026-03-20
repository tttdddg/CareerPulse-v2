<template>
  <el-upload
    class="resume-upload"
    drag
    :accept="accept"
    :multiple="multiple"
    :show-file-list="showFileList"
    :before-upload="beforeUpload"
    :http-request="handleRequest"
  >
    <el-icon class="upload-icon"><Upload /></el-icon>
    <div class="upload-text">
      <p>拖拽简历到此处，或点击上传</p>
      <span>支持 PDF / Word，单文件不超过 {{ maxSizeMB }}MB</span>
    </div>
    <template #tip>
      <div class="el-upload__tip">上传后可自动解析简历信息</div>
    </template>
  </el-upload>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { Upload } from '@element-plus/icons-vue'
import type { UploadRawFile, UploadRequestHandler, UploadRequestOptions } from 'element-plus'

export interface ResumeUploadPayload {
  formData: FormData
  file: File
  options: UploadRequestOptions
  onSuccess: (response?: unknown) => void
  onError: (error: Error) => void
}

export interface ResumeUploadProps {
  accept?: string
  multiple?: boolean
  maxSizeMB?: number
  fieldName?: string
  showFileList?: boolean
}

const props = withDefaults(defineProps<ResumeUploadProps>(), {
  accept: '.pdf,.doc,.docx',
  multiple: false,
  maxSizeMB: 8,
  fieldName: 'file',
  showFileList: true
})

const emit = defineEmits<{
  (event: 'upload', payload: ResumeUploadPayload): void
  (event: 'error', message: string): void
}>()

// 文件类型校验
const isValidType = (file: UploadRawFile): boolean => {
  const acceptList = props.accept
    .split(',')
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean)

  if (acceptList.length === 0) {
    return true
  }

  const fileName = file.name.toLowerCase()
  return acceptList.some((type) => fileName.endsWith(type))
}

// 文件大小校验
const isValidSize = (file: UploadRawFile): boolean => {
  const sizeMB = file.size / 1024 / 1024
  return sizeMB <= props.maxSizeMB
}

const beforeUpload = (file: UploadRawFile): boolean => {
  if (!isValidType(file)) {
    const message = '文件格式不支持，请上传 PDF 或 Word'
    ElMessage.error(message)
    emit('error', message)
    return false
  }

  if (!isValidSize(file)) {
    const message = `文件大小超过 ${props.maxSizeMB}MB 限制`
    ElMessage.error(message)
    emit('error', message)
    return false
  }

  return true
}

// 统一处理 FormData，并交给外部上传
const handleRequest: UploadRequestHandler = async (options: UploadRequestOptions) => {
  const formData = new FormData()
  formData.append(props.fieldName, options.file)
  return new Promise((resolve, reject) => {
    const resolveUpload = (response?: unknown): void => {
      const result = response ?? { ok: true }
      options.onSuccess?.(result)
      resolve(result)
    }

    const rejectUpload = (error: Error): void => {
      options.onError?.(error)
      reject(error)
    }

    try {
      emit('upload', {
        formData,
        file: options.file,
        options,
        onSuccess: resolveUpload,
        onError: rejectUpload
      })
    } catch (error) {
      rejectUpload(error instanceof Error ? error : new Error('上传失败'))
    }
  })
}
</script>

<style scoped>
.resume-upload {
  width: 100%;
}

.upload-icon {
  font-size: 32px;
  color: var(--cp-primary);
}

.upload-text {
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: var(--cp-text-muted);
}

.upload-text p {
  margin: 0;
  font-weight: 600;
  color: var(--cp-text);
}
</style>
