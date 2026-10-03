# Слой 0: машина, на которой будет жить стенд.
#
# Terraform здесь делает ровно одно — создаёт хост. Дальше его забирает
# Ansible (site.yml), который ставит Docker, containerlab и окружение проекта.
# Разделение не ради красоты: топологию стенда поднимает containerlab, и
# тащить её в Terraform значило бы описывать одно и то же дважды.
#
# Провайдер libvirt выбран сознательно: локальный KVM, без облачного счёта и
# без ключей в репозитории, и `terraform apply` действительно отрабатывает.
# Облачный вариант — в cloud.tf.example, он требует своих секретов.

terraform {
  required_version = ">= 1.6"
  required_providers {
    libvirt = {
      source  = "dmacvicar/libvirt"
      version = "~> 0.7"
    }
  }
}

provider "libvirt" {
  uri = var.libvirt_uri
}

resource "libvirt_volume" "base" {
  name   = "${var.name}-base.qcow2"
  pool   = var.pool
  source = var.image_url
  format = "qcow2"
}

resource "libvirt_volume" "disk" {
  name           = "${var.name}.qcow2"
  pool           = var.pool
  base_volume_id = libvirt_volume.base.id
  size           = var.disk_bytes
}

# Вложенная виртуализация не нужна: узлы стенда — контейнеры, а не ВМ.
# Памяти берём с запасом под образы узлов, а не под гипервизор.
resource "libvirt_domain" "bench" {
  name   = var.name
  memory = var.memory_mb
  vcpu   = var.vcpus

  cloudinit = libvirt_cloudinit_disk.init.id

  disk {
    volume_id = libvirt_volume.disk.id
  }

  network_interface {
    network_name   = var.network
    wait_for_lease = true
  }

  console {
    type        = "pty"
    target_port = "0"
  }
}

resource "libvirt_cloudinit_disk" "init" {
  name = "${var.name}-init.iso"
  pool = var.pool
  user_data = templatefile("${path.module}/cloud-init.yml.tftpl", {
    user    = var.ssh_user
    ssh_key = file(var.ssh_public_key)
  })
}
