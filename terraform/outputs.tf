output "server_public_ip" {
  value = aws_instance.app_server.public_ip
}

output "app_url" {
  value = "http://${aws_instance.app_server.public_ip}:5000"
}

output "grafana_url" {
  value = "http://${aws_instance.app_server.public_ip}:3000"
}
