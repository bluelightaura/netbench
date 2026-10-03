# Выход один и ровно тот, что нужен следующему слою: адрес, по которому
# Ansible заберёт машину.
output "address" {
  description = "Адрес машины под стенд"
  value       = libvirt_domain.bench.network_interface[0].addresses[0]
}

output "ansible_line" {
  description = "Готовая строка для lab/provision/inventory.ini"
  value = format(
    "%s ansible_host=%s ansible_user=%s",
    var.name,
    libvirt_domain.bench.network_interface[0].addresses[0],
    var.ssh_user,
  )
}
