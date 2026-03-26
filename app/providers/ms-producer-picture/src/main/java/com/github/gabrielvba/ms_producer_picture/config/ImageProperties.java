package com.github.gabrielvba.ms_producer_picture.config;

import java.util.Map;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "image.files")
public class ImageProperties {

	private Map<String, String> binary;
	private Map<String, String> base64;

	public Map<String, String> getBinary() {
		return binary;
	}

	public void setBinary(Map<String, String> binary) {
		this.binary = binary;
	}

	public Map<String, String> getBase64() {
		return base64;
	}

	public void setBase64(Map<String, String> base64) {
		this.base64 = base64;
	}
}

