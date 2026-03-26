package com.github.gabrielvba.ms_producer_picture;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

import org.springframework.boot.context.properties.EnableConfigurationProperties;

import com.github.gabrielvba.ms_producer_picture.config.ImageProperties;

@SpringBootApplication
@EnableConfigurationProperties(ImageProperties.class)
public class MsProducerPictureApplication {

	public static void main(String[] args) {
		SpringApplication.run(MsProducerPictureApplication.class, args);
	}
}

