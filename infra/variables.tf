variable "name" {
  description = "Имя машины под стенд"
  type        = string
  default     = "bench"
}

variable "libvirt_uri" {
  description = "Куда подключаться libvirt"
  type        = string
  default     = "qemu:///system"
}

variable "pool" {
  description = "Пул хранилища libvirt"
  type        = string
  default     = "default"
}

variable "network" {
  description = "Сеть libvirt"
  type        = string
  default     = "default"
}

variable "image_url" {
  description = "Облачный образ системы"
  type        = string
  default     = "https://cloud.debian.org/images/cloud/bookworm/latest/debian-12-generic-amd64.qcow2"
}

variable "disk_bytes" {
  description = "Размер диска. Образы узлов стенда занимают заметно."
  type        = number
  default     = 21474836480 # 20 ГиБ
}

variable "memory_mb" {
  description = "Память. Два-три узла FRR живут спокойно, десяток — нет."
  type        = number
  default     = 4096
}

variable "vcpus" {
  type    = number
  default = 2
}

variable "ssh_user" {
  description = "Пользователь, которого заберёт Ansible"
  type        = string
  default     = "bench"
}

variable "ssh_public_key" {
  description = "Открытый ключ для входа. Закрытый в репозиторий не кладём."
  type        = string
  default     = "~/.ssh/id_ed25519.pub"
}
