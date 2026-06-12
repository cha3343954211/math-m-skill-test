function [I] = anliepingtu(cell,xu)


for i = 1:length(xu)      %length(xu)
    I(180*(i-1)+1:180*i,:)=cell{1,xu(i)};       %½«Í¼¸´Ô­
end



end

